<#
  Parakh - move the project from C: to D: (and rename it).

  What it does
    1. Finds the project folder (default C:\Users\dellg15\quantpulse-ai) and any
       other "quantpulse" folders in your user profile (Desktop, Documents,
       Downloads, OneDrive), and shows you what it found.
    2. Checks D: exists and has enough free space.
    3. Copies everything to D:\Parakh\parakh (each extra folder goes next to it),
       skipping only rebuildable caches (.next, __pycache__, .pytest_cache).
    4. Verifies every file arrived (count + total size).
    5. Only after verification, and only if you type YES, deletes the C: copy.
    6. Optionally clears the npm and pip download caches on C:.

  Nothing is deleted without your confirmation. Safe to re-run.
#>
param(
  [string]$Source = "C:\Users\dellg15\quantpulse-ai",
  [string]$DestRoot = "D:\Parakh",
  [string]$NewName = "parakh"
)

$ErrorActionPreference = "Stop"
function Say($msg, $color = "White") { Write-Host $msg -ForegroundColor $color }
function SizeOf($path, $excludeDirs) {
  $files = Get-ChildItem -LiteralPath $path -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $p = $_.FullName; -not ($excludeDirs | Where-Object { $p -like "*\$_\*" }) }
  [pscustomobject]@{ Count = ($files | Measure-Object).Count; Bytes = ($files | Measure-Object Length -Sum).Sum }
}

$Exclude = @(".next", "__pycache__", ".pytest_cache")

Say "`n=== Parakh: move project from C: to D: ===`n" Cyan

# 1. Find folders ------------------------------------------------------------
$candidates = New-Object System.Collections.Generic.List[string]
if (Test-Path -LiteralPath $Source) { $candidates.Add((Resolve-Path -LiteralPath $Source).Path) }
$searchRoots = @("$env:USERPROFILE\Desktop", "$env:USERPROFILE\Documents", "$env:USERPROFILE\Downloads",
                 "$env:USERPROFILE\OneDrive", "$env:USERPROFILE")
foreach ($root in $searchRoots) {
  if (-not (Test-Path -LiteralPath $root)) { continue }
  Get-ChildItem -LiteralPath $root -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "quantpulse" } |
    ForEach-Object { if (-not $candidates.Contains($_.FullName)) { $candidates.Add($_.FullName) } }
}
if ($candidates.Count -eq 0) {
  Say "Couldn't find $Source or any 'quantpulse' folder in your profile." Yellow
  $manual = Read-Host "Paste the full path of the project folder (or press Enter to quit)"
  if (-not $manual -or -not (Test-Path -LiteralPath $manual)) { Say "Nothing to do."; exit 1 }
  $candidates.Add((Resolve-Path -LiteralPath $manual).Path)
}

Say "Found these folders on C:" Green
$i = 0
foreach ($c in $candidates) {
  $s = SizeOf $c @()
  $i++
  Say ("  [{0}] {1}  ({2:N0} files, {3:N1} MB)" -f $i, $c, $s.Count, ($s.Bytes / 1MB))
}

# 2. Check D: ----------------------------------------------------------------
if (-not (Test-Path "D:\")) { Say "`nD: drive not found. Plug it in / check Disk Management, then re-run." Red; exit 1 }
$need = ($candidates | ForEach-Object { (SizeOf $_ @()).Bytes } | Measure-Object -Sum).Sum
$free = (Get-PSDrive -Name D).Free
Say ("`nNeed about {0:N1} MB; D: has {1:N1} GB free." -f ($need / 1MB), ($free / 1GB))
if ($free -lt ($need * 1.1)) { Say "Not enough space on D:." Red; exit 1 }

Say "`nPlan:" Cyan
$plan = @()
for ($k = 0; $k -lt $candidates.Count; $k++) {
  $src = $candidates[$k]
  $dst = if ($k -eq 0) { Join-Path $DestRoot $NewName } else { Join-Path $DestRoot (Split-Path $src -Leaf) }
  $plan += [pscustomobject]@{ Src = $src; Dst = $dst }
  Say "  $src  ->  $dst"
}
Say "  (skipping rebuildable caches: $($Exclude -join ', '))"
$go = Read-Host "`nStart copying? (y/n)"
if ($go -notin @("y", "Y", "yes", "YES")) { Say "Cancelled. Nothing changed."; exit 0 }

# 3-4. Copy + verify ---------------------------------------------------------
$allOk = $true
foreach ($p in $plan) {
  Say "`nCopying $($p.Src) ..." Cyan
  New-Item -ItemType Directory -Force -Path $p.Dst | Out-Null
  $xd = @(); foreach ($e in $Exclude) { $xd += $e }
  robocopy $p.Src $p.Dst /E /COPY:DAT /DCOPY:T /R:2 /W:2 /XJ /NFL /NDL /NP /XD $xd | Out-Host
  if ($LASTEXITCODE -ge 8) { Say "robocopy reported errors for $($p.Src)." Red; $allOk = $false; continue }
  $a = SizeOf $p.Src $Exclude
  $b = SizeOf $p.Dst $Exclude
  if ($a.Count -eq $b.Count -and $a.Bytes -eq $b.Bytes) {
    Say ("  Verified: {0:N0} files, {1:N1} MB match." -f $b.Count, ($b.Bytes / 1MB)) Green
  } else {
    Say ("  MISMATCH: C: {0} files/{1} bytes vs D: {2} files/{3} bytes" -f $a.Count, $a.Bytes, $b.Count, $b.Bytes) Red
    $allOk = $false
  }
}
if (-not $allOk) { Say "`nSomething didn't verify, so nothing was deleted from C:. Fix and re-run." Red; exit 1 }

# 5. Delete originals (confirmed) -------------------------------------------
Say "`nEverything is safely on D:. Close VS Code / terminals using the old folder first." Yellow
$del = Read-Host "Type YES to delete the originals from C: (anything else keeps them)"
if ($del -ceq "YES") {
  foreach ($p in $plan) {
    try { Remove-Item -LiteralPath $p.Src -Recurse -Force; Say "  Deleted $($p.Src)" Green }
    catch { Say "  Couldn't delete $($p.Src) (a file is open?). Close programs and delete it manually." Yellow }
  }
} else { Say "Kept the C: copies. You can delete them later." }

# 6. Optional cache cleanup ---------------------------------------------------
$c = Read-Host "`nAlso clear npm + pip download caches on C: (frees space, safe)? (y/n)"
if ($c -in @("y", "Y")) {
  if (Get-Command npm -ErrorAction SilentlyContinue) { npm cache clean --force | Out-Host }
  if (Get-Command pip -ErrorAction SilentlyContinue) { pip cache purge | Out-Host }
}

$main = $plan[0].Dst
Say "`nDone. Your project is now at: $main" Green
Say "Next time:  cd `"$main`"  then  git pull  to get the latest Parakh code." Cyan
Say "Tip: point npm/pip caches at D: too:  npm config set cache D:\Parakh\.npm-cache   and   pip config set global.cache-dir D:\Parakh\.pip-cache`n"
Read-Host "Press Enter to close"

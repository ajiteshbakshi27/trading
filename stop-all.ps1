# Parakh — stop everything (backend :8000, frontend :3000, wrangler :5000, tunnel).
# Right-click -> "Run with PowerShell" (or: powershell -ExecutionPolicy Bypass -File stop-all.ps1)
foreach ($port in 8000, 3000, 5000) {
    netstat -ano | Select-String ":$port.*LISTENING" |
        ForEach-Object { ($_ -split '\s+')[-1] } |
        Sort-Object -Unique |
        ForEach-Object { taskkill /F /PID $_ 2>$null }
}
taskkill /F /IM cloudflared.exe 2>$null
taskkill /F /IM wrangler.exe 2>$null
Write-Host 'All Parakh servers stopped.'

# QuantPulse AI — start everything at once.
# Right-click -> "Run with PowerShell" (or: powershell -ExecutionPolicy Bypass -File start-all.ps1)
# Leaves 3 windows open: backend :8000, tunnel, frontend :3000. Close them to stop.
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root\backend'; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"

Start-Process powershell -ArgumentList '-NoExit', '-Command', "& 'C:\Program Files (x86)\cloudflared\cloudflared.exe' tunnel --url http://localhost:8000"

Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root\frontend'; npm run dev -- --port 3000"

# Optional: Indian-API sidecar (native Yahoo works without it — uncomment if wanted).
# Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root\Indian-Stock-Market-API'; npx wrangler dev --port 5000"

Write-Host ''
Write-Host 'Started: backend :8000, tunnel, frontend :3000.'
Write-Host 'Site: http://localhost:3000  |  Health: http://localhost:8000/health'
Write-Host 'Stop everything with stop-all.ps1 (or close the 3 windows).'

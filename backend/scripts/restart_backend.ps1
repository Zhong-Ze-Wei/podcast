$ErrorActionPreference = "SilentlyContinue"
$backend = "E:\ZZ's_Code\AI\podcast\backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"
$existing = Get-NetTCPConnection -LocalPort 5000 -State Listen | Select-Object -First 1
if ($existing) {
  Stop-Process -Id $existing.OwningProcess -Force
  Start-Sleep -Seconds 2
}
Start-Process -WindowStyle Hidden -FilePath $python -ArgumentList "run.py" -WorkingDirectory $backend
Start-Sleep -Seconds 8
$again = Get-NetTCPConnection -LocalPort 5000 -State Listen | Select-Object -First 1
if ($again) { Write-Output ("BACKEND_UP pid=" + $again.OwningProcess) } else { Write-Output "BACKEND_DOWN" }

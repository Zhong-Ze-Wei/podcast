Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*backfill_with_cookies*" } | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force
  Write-Output ("killed " + $_.ProcessId)
}

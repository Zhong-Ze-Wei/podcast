# Keep Docker's Windows sockets on a real C: directory; reuse existing E: data.
# No reset, deletion, or database migration. Works with Windows PowerShell 5.1+.
$ErrorActionPreference = 'Stop'
$runtimeRoot = Join-Path $env:USERPROFILE 'DockerLocalRuntime'
$dataRoot = 'E:\docker'
if (-not (Test-Path -LiteralPath "$dataRoot\wsl\disk\docker_data.vhdx")) {
    throw 'Existing Docker data disk was not found; refusing to initialize an empty Docker instance.'
}
if (Get-Process -Name 'com.docker.backend' -ErrorAction SilentlyContinue) {
    Write-Output 'Docker is already running. Quit Docker before switching its runtime directory.'
    exit 0
}
# This directory passed a same-directory rename probe. The AppData location on
# this machine fails that operation, which also stops Docker's backup scheduler.
$dockerRoot = Join-Path $runtimeRoot 'Docker'
New-Item -ItemType Directory -Path "$dockerRoot\run" -Force | Out-Null
foreach ($name in @('wsl', 'tasks')) {
    $link = Join-Path $dockerRoot $name
    $target = Join-Path $dataRoot $name
    if (Test-Path -LiteralPath $link) {
        $existing = Get-Item -LiteralPath $link
        if ($existing.LinkType -ne 'Junction' -or $existing.Target -ne $target) {
            throw "Unexpected data mapping: $link"
        }
    } else {
        New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    }
}
$previousLocalAppData = $env:LOCALAPPDATA
try {
    # The override is inherited only by the launched process, not saved to Windows settings.
    $env:LOCALAPPDATA = $runtimeRoot
    Start-Process -FilePath 'C:\Program Files\Docker\Docker\Docker Desktop.exe' -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeRoot 'launcher.stdout.log') `
        -RedirectStandardError (Join-Path $runtimeRoot 'launcher.stderr.log')
} finally {
    $env:LOCALAPPDATA = $previousLocalAppData
}
Write-Output 'Docker launched with local runtime files and the existing E: data disk.'

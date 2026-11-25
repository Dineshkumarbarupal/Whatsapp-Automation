param(
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$appRoot = Join-Path $repoRoot "WhatsappAutomation/py.26.09.21/theme/WhatsappAutomation_Basic/User"
$iconPath = Join-Path $appRoot "asset/logo.ico"
$pythonVenv = Join-Path $repoRoot ".venv/Scripts/python.exe"
$mainPath = Join-Path $appRoot "main.py"
$exePath = Join-Path $repoRoot "dist/WhatsAppWorkspace/WhatsAppWorkspace.exe"

if (-not (Test-Path $appRoot)) {
    throw "Application source folder was not found: $appRoot"
}
if (-not (Test-Path $iconPath)) {
    throw "Windows icon file was not found: $iconPath"
}

if (-not (Test-Path $pythonVenv)) {
    Write-Host "Creating project virtual environment..."
    py -3 -m venv (Join-Path $repoRoot ".venv")
}
if (-not (Test-Path $pythonVenv)) {
    throw "Python 3 was not found. Install Python 3.10+ and retry."
}

if (-not $SkipDependencyInstall) {
    & $pythonVenv -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip." }

    & $pythonVenv -m pip install -r (Join-Path $repoRoot "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Could not install application requirements." }

    & $pythonVenv -m pip install "pyinstaller>=6.0,<7.0"
    if ($LASTEXITCODE -ne 0) { throw "Could not install PyInstaller." }
}

Write-Host "Building WhatsApp Workspace with logo.ico..."
$buildArgs = @(
    "--noconfirm",
    "--clean",
    "--onedir",
    "--windowed",
    "--name", "WhatsAppWorkspace",
    "--icon", $iconPath,
    "--add-data", "$appRoot;User",
    "--paths", $appRoot,
    "--collect-all", "eel",
    "--collect-all", "bottle",
    "--collect-all", "bottle_websocket",
    "--distpath", (Join-Path $repoRoot "dist"),
    "--workpath", (Join-Path $repoRoot "build"),
    "--specpath", (Join-Path $repoRoot "build"),
    $mainPath
)
& $pythonVenv -m PyInstaller @buildArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed. Review the build output above."
}
if (-not (Test-Path $exePath)) {
    throw "Build completed but executable was not found: $exePath"
}

$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "WhatsApp Workspace.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = Split-Path $exePath
$shortcut.IconLocation = "$exePath,0"
$shortcut.Description = "WhatsApp Workspace desktop application"
$shortcut.Save()

Write-Host ""
Write-Host "Build completed."
Write-Host "Executable: $exePath"
Write-Host "Desktop shortcut: $shortcutPath"
Write-Host "The shortcut uses the embedded logo.ico application icon."

$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "Score Extractor.lnk"

$pyExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pyExe) { $pyExe = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
if (-not $pyExe) { $pyExe = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $pyExe) {
    Write-Host "Python not found on PATH." -ForegroundColor Red
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath       = $pyExe
$shortcut.Arguments        = "`"$(Join-Path $PSScriptRoot 'app_gui.py')`""
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Description      = "Score Extractor"
$shortcut.Save()

Write-Host "Desktop shortcut created: $shortcutPath" -ForegroundColor Green

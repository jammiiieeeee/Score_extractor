param(
    [string]$UpxDir = "C:\upx"
)

Write-Host "Building Score Extractor executable..." -ForegroundColor Cyan

$common = @(
    "--onefile",
    "--windowed",
    "--name", "ScoreExtractor",
    "--version-file", "version.txt",
    "--noconfirm"
)

# PyQt6 modules we DON'T use — exclude to save ~50 MB
$excludes = @(
    "PyQt6.QtBluetooth",
    "PyQt6.QtCharts",
    "PyQt6.QtDataVisualization",
    "PyQt6.QtHelp",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    "PyQt6.QtNfc",
    "PyQt6.QtPositioning",
    "PyQt6.QtQml",
    "PyQt6.QtQmlModels",
    "PyQt6.QtQuick",
    "PyQt6.QtQuick3D",
    "PyQt6.QtRemoteObjects",
    "PyQt6.QtScxml",
    "PyQt6.QtSensors",
    "PyQt6.QtSerialPort",
    "PyQt6.QtSql",
    "PyQt6.QtStateMachine",
    "PyQt6.QtSvgWidgets",
    "PyQt6.QtTextToSpeech",
    "PyQt6.QtTest",
    "PyQt6.QtWebChannel",
    "PyQt6.QtWebEngine",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebSockets",
    "PyQt6.QtXml",
    "PyQt6.QtDBus"
)

$upxFlag = ""
if (Test-Path (Join-Path $UpxDir "upx.exe")) {
    $upxFlag = "--upx-dir=$UpxDir"
    Write-Host "UPX found at $UpxDir, compression enabled." -ForegroundColor Green
} else {
    Write-Host "UPX not found at $UpxDir." -ForegroundColor Yellow
    Write-Host "Download from https://github.com/upx/upx/releases/latest" -ForegroundColor Yellow
}

$excludeArgs = $excludes | ForEach-Object { "--exclude-module", $_ }
$args = $common + $excludeArgs + @($upxFlag, "--clean", "app_gui.py") | Where-Object { $_ -ne "" }

Write-Host "Running: pyinstaller $($args -join ' ')" -ForegroundColor Gray
pyinstaller $args

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nBuild complete!" -ForegroundColor Green
    Write-Host "Executable at: dist\ScoreExtractor.exe" -ForegroundColor Green
} else {
    Write-Host "`nBuild failed with exit code $LASTEXITCODE." -ForegroundColor Red
}

param(
    [string]$UpxDir = "C:\upx"
)

Write-Host "Building Score Extractor executable..." -ForegroundColor Cyan

pip install pyinstaller

$upxFlag = ""
if (Test-Path $UpxDir) {
    $upxFlag = "--upx-dir=`"$UpxDir`""
    Write-Host "UPX found at $UpxDir, compression enabled." -ForegroundColor Green
} else {
    Write-Host "UPX not found at $UpxDir. Install UPX from https://upx.github.io/ for smaller executable size." -ForegroundColor Yellow
}

$cmd = "pyinstaller --onefile --windowed --name ScoreExtractor $upxFlag app_gui.py"
Write-Host "Running: $cmd" -ForegroundColor Gray
Invoke-Expression $cmd

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nBuild complete!" -ForegroundColor Green
    Write-Host "Executable at: dist\ScoreExtractor.exe" -ForegroundColor Green
} else {
    Write-Host "`nBuild failed." -ForegroundColor Red
}

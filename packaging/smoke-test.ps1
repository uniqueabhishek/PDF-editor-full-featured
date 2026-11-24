<#
.SYNOPSIS
    Check a packaged Open PDF Editor exe end to end without a screen.

.DESCRIPTION
    Starts the exe with OPEN_PDF_SMOKE_TEST pointing at a small generated PDF and a
    throwaway home folder, so real settings are never touched. The app opens the
    file, waits for the render process to draw the first page and exits 0.
    Fails (exit 1) on any other exit code, a missing "SMOKE OK" log line, or a hang.

.EXAMPLE
    pwsh packaging/smoke-test.ps1 -Exe "dist\Open PDF Editor\Open PDF Editor.exe"
#>
param(
    [Parameter(Mandatory)] [string] $Exe,
    [int] $TimeoutSeconds = 120
)
$ErrorActionPreference = 'Stop'

$exePath = (Resolve-Path $Exe).Path
$home_ = Join-Path ([IO.Path]::GetTempPath()) ("open-pdf-smoke-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $home_ | Out-Null
$pdf = Join-Path $home_ 'sample.pdf'

# A minimal valid one-page PDF, so this script needs nothing but PowerShell.
$body = "%PDF-1.4`n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj`n" +
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj`n" +
        "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj`n" +
        "trailer<</Root 1 0 R>>`n%%EOF`n"
[IO.File]::WriteAllText($pdf, $body)

$env:OPEN_PDF_SMOKE_TEST = $pdf
$env:QT_QPA_PLATFORM = 'offscreen'
$env:USERPROFILE = $home_
$env:HOME = $home_

$watch = [Diagnostics.Stopwatch]::StartNew()
$proc = Start-Process -FilePath $exePath -PassThru
if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
    Stop-Process $proc -Force
    throw "Smoke test hung for $TimeoutSeconds s: $exePath"
}
$log = Join-Path $home_ '.open_pdf_editor\open_pdf_editor.log'
$text = if (Test-Path $log) { Get-Content $log -Raw } else { '(no log written)' }
Write-Host $text
Write-Host ("Exit code {0} after {1:N1} s" -f $proc.ExitCode, $watch.Elapsed.TotalSeconds)
Remove-Item $home_ -Recurse -Force -ErrorAction SilentlyContinue

if ($proc.ExitCode -ne 0 -or $text -notmatch 'SMOKE OK') {
    Write-Error "Smoke test failed: $exePath"
    exit 1
}
Write-Host "Smoke test passed: $exePath"

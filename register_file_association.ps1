<#
.SYNOPSIS
    Register Ultra PDF Editor as a per-user handler for .pdf files and create a
    Desktop shortcut.

.DESCRIPTION
    Adds a per-user (HKCU) ProgID so Windows can open PDFs in Ultra PDF Editor,
    lists the app in the right-click "Open with" menu, and drops a Desktop
    shortcut that launches the editor with no document.

    No administrator rights are needed (everything lives under HKCU). Windows
    protects the *default* PDF handler with a per-user hash, so this script
    cannot silently make Ultra PDF Editor the default. After running it, set the
    default once by hand:

        Right-click any .pdf -> Open with -> Choose another app ->
        Ultra PDF Editor -> check "Always" -> OK.

.PARAMETER Unregister
    Remove everything this script creates (ProgID, Open-With entry, shortcut).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\register_file_association.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\register_file_association.ps1 -Unregister
#>
[CmdletBinding()]
param(
    [switch]$Unregister
)

$ErrorActionPreference = 'Stop'

# --- Resolve paths relative to this script so the project can be moved -------
$ProjectDir  = $PSScriptRoot
$Pythonw     = Join-Path $ProjectDir '.venv\Scripts\pythonw.exe'
$EntryScript = Join-Path $ProjectDir 'Ultra_PDF_Editor.py'
$IconPath    = Join-Path $ProjectDir 'resources\assets\UltraPDF.ico'

$ProgId        = 'UltraPDFEditor.pdf'
$ProgIdKey     = "HKCU:\Software\Classes\$ProgId"
$OpenWithKey   = 'HKCU:\Software\Classes\.pdf\OpenWithProgids'
$ShortcutPath  = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Ultra PDF Editor.lnk'

function Remove-Registration {
    if (Test-Path $ProgIdKey) {
        Remove-Item $ProgIdKey -Recurse -Force
        Write-Host "Removed ProgID $ProgId"
    }
    if (Test-Path $OpenWithKey) {
        $prop = Get-ItemProperty $OpenWithKey -ErrorAction SilentlyContinue
        if ($prop -and $prop.PSObject.Properties.Name -contains $ProgId) {
            Remove-ItemProperty $OpenWithKey -Name $ProgId -Force
            Write-Host "Removed Open-With entry for .pdf"
        }
    }
    if (Test-Path $ShortcutPath) {
        Remove-Item $ShortcutPath -Force
        Write-Host "Removed Desktop shortcut"
    }
    Write-Host "`nUnregistered. Windows may still list Ultra PDF Editor under" `
        "'Open with' until you pick a different default for .pdf once."
}

function New-Registration {
    if (-not (Test-Path $Pythonw))     { throw "pythonw.exe not found at $Pythonw - run 'uv sync' first." }
    if (-not (Test-Path $EntryScript)) { throw "Entry script not found at $EntryScript" }

    $command = '"{0}" "{1}" "%1"' -f $Pythonw, $EntryScript

    # ProgID: friendly type name + open command
    New-Item -Path $ProgIdKey -Force | Out-Null
    Set-ItemProperty -Path $ProgIdKey -Name '(default)' -Value 'PDF Document'

    $cmdKey = Join-Path $ProgIdKey 'shell\open\command'
    New-Item -Path $cmdKey -Force | Out-Null
    Set-ItemProperty -Path $cmdKey -Name '(default)' -Value $command

    # A friendly label for the "Open with" list
    Set-ItemProperty -Path (Join-Path $ProgIdKey 'shell\open') -Name 'FriendlyAppName' -Value 'Ultra PDF Editor'

    # Icon shown for PDFs handled by this ProgID (and in the Open-With list)
    if (Test-Path $IconPath) {
        $iconKey = Join-Path $ProgIdKey 'DefaultIcon'
        New-Item -Path $iconKey -Force | Out-Null
        Set-ItemProperty -Path $iconKey -Name '(default)' -Value ('"{0}",0' -f $IconPath)
    } else {
        Write-Warning "Icon not found at $IconPath - the file association will use a generic icon."
    }

    # Add to the .pdf "Open with" candidates (does NOT change the default)
    New-Item -Path $OpenWithKey -Force | Out-Null
    Set-ItemProperty -Path $OpenWithKey -Name $ProgId -Value ''

    Write-Host "Registered ProgID '$ProgId' with command:"
    Write-Host "  $command"

    # --- Desktop shortcut (launches the editor with no document) ------------
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($ShortcutPath)
    $lnk.TargetPath       = $Pythonw
    $lnk.Arguments        = '"{0}"' -f $EntryScript
    $lnk.WorkingDirectory = $ProjectDir
    $lnk.Description       = 'Ultra PDF Editor'
    if (Test-Path $IconPath) { $lnk.IconLocation = ('{0},0' -f $IconPath) }
    $lnk.Save()
    Write-Host "Created Desktop shortcut: $ShortcutPath"

    # Nudge Explorer to refresh association/icon caches
    try {
        Add-Type -Namespace Win32 -Name Shell -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("shell32.dll")]
public static extern void SHChangeNotify(int eventId, int flags, System.IntPtr item1, System.IntPtr item2);
'@ -ErrorAction SilentlyContinue
        [Win32.Shell]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero) # SHCNE_ASSOCCHANGED
    } catch { }

    Write-Host ""
    Write-Host "Next step (one time): right-click any .pdf -> Open with ->"
    Write-Host "Choose another app -> 'Ultra PDF Editor' -> check 'Always'."
}

if ($Unregister) { Remove-Registration } else { New-Registration }

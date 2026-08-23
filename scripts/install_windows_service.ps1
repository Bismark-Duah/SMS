# ================================================================
# SMS Windows Auto-Start Installer Script
# Configures SMS Backend to start automatically on Windows boot/login
# ================================================================

$ProjectDir = Split-Path -Path $PSScriptRoot -Parent
$ScriptPath = Join-Path -Path $PSScriptRoot -ChildPath "start_server_background.bat"
$StartupFolder = [System.IO.Path]::Combine($env:APPDATA, "Microsoft\Windows\Start Menu\Programs\Startup")
$ShortcutPath = [System.IO.Path]::Combine($StartupFolder, "SMS_Backend_AutoStart.lnk")

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Configured SMS Windows Auto-Start Launcher      " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

try {
    # Create Windows Startup Shortcut (Zero admin permissions required)
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $ScriptPath
    $Shortcut.WorkingDirectory = $ProjectDir
    $Shortcut.WindowStyle = 7 # Minimized / Hidden
    $Shortcut.Description = "School Management System FastAPI Server Auto-Start"
    $Shortcut.Save()

    Write-Host "[SUCCESS] Auto-Start Shortcut created in Windows Startup Folder:" -ForegroundColor Green
    Write-Host "          $ShortcutPath" -ForegroundColor Yellow
    Write-Host "[INFO] The SMS Backend will now start automatically whenever the computer logs in/boots!" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to create startup shortcut: $_" -ForegroundColor Red
}

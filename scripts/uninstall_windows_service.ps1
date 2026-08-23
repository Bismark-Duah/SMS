# ================================================================
# SMS Windows Service Uninstaller Script
# Unregisters SMS_BackendService from Windows Task Scheduler
# ================================================================

$TaskName = "SMS_BackendService"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Unregistering SMS Auto-Start Background Service  " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "[SUCCESS] Task '$TaskName' removed successfully." -ForegroundColor Green
} else {
    Write-Host "[INFO] Task '$TaskName' was not found." -ForegroundColor Yellow
}

# setup_backup_task.ps1
# Run this ONCE as Administrator to register the nightly backup with Windows Task Scheduler.
# After running, the backup will fire automatically at 2:00 AM every day.

$TaskName   = "SMS_NightlyBackup"
$ScriptPath = "d:\documents\my apps\SMS\scripts\automated_backup.ps1"
$LogDir     = "d:\documents\my apps\SMS\logs"

# Remove old task if it exists
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task: $TaskName"
}

$action  = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory "d:\documents\my apps\SMS"

$trigger = New-ScheduledTaskTrigger -Daily -At "02:00AM"

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask `
    -TaskName  $TaskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -RunLevel  Highest `
    -Force

Write-Host ""
Write-Host "✅ Task '$TaskName' registered successfully."
Write-Host "   Runs: Daily at 2:00 AM"
Write-Host "   Script: $ScriptPath"
Write-Host "   Logs: $LogDir\backup.log"
Write-Host ""
Write-Host "IMPORTANT: You must save an admin JWT token to:"
Write-Host "   $LogDir\backup_token.txt"
Write-Host "Get this token by logging in as admin and copying your accessToken from browser localStorage."

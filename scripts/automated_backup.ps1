# automated_backup.ps1
# Runs nightly via Windows Task Scheduler to back up the SMS database.
# Schedule: Registered by setup_backup_task.ps1 — runs at 2:00 AM daily.

$ServerUrl   = "http://127.0.0.1:8000"
$BackupDir   = "d:\documents\my apps\SMS\backups"
$LogFile     = "d:\documents\my apps\SMS\logs\backup.log"
$TokenFile   = "d:\documents\my apps\SMS\logs\backup_token.txt"

function Write-Log($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "[$timestamp] $msg"
}

# Ensure directories exist
New-Item -ItemType Directory -Force -Path (Split-Path $LogFile) | Out-Null
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

Write-Log "--- Nightly backup started ---"

# Check server is running
try {
    $ping = Invoke-RestMethod -Uri "$ServerUrl/api/settings/" -Method Get -TimeoutSec 10 -ErrorAction Stop
} catch {
    Write-Log "ERROR: Server not reachable at $ServerUrl. Backup aborted."
    exit 1
}

# Read token from file (written there by the startup script or manually)
if (-not (Test-Path $TokenFile)) {
    Write-Log "ERROR: No backup token found at $TokenFile. Run the server and save an admin token there."
    exit 1
}
$Token = (Get-Content $TokenFile -Raw).Trim()

# Trigger backup via API
try {
    $result = Invoke-RestMethod `
        -Uri "$ServerUrl/api/backup/run" `
        -Method Post `
        -Headers @{ Authorization = "Bearer $Token" } `
        -TimeoutSec 60 `
        -ErrorAction Stop

    Write-Log "SUCCESS: Backup created — $($result.filename) ($([math]::Round($result.size_bytes/1KB, 1)) KB)"
} catch {
    Write-Log "ERROR: Backup API call failed — $($_.Exception.Message)"
    exit 1
}

# Prune backups older than 30 days
$cutoff = (Get-Date).AddDays(-30)
Get-ChildItem -Path $BackupDir -Filter "backup_*.db" |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    ForEach-Object {
        Remove-Item $_.FullName -Force
        Write-Log "PRUNED: $($_.Name) (older than 30 days)"
    }

Write-Log "--- Nightly backup completed ---"

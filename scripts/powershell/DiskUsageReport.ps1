<#
.SYNOPSIS
    Generates a disk usage report for local drives and optionally
    alerts when free space is low.
.DESCRIPTION
    Retrieves the total size, free space and percentage of free space for
    each fixed disk on the local computer. Specific drives can be
    targeted and a warning is issued when the free space percentage
    falls below the configured threshold. Results can be exported to
    CSV and an alert email can be sent.
.PARAMETER Volume
    Array of drive letters to include in the report (e.g. C, D).
.PARAMETER AlertThreshold
    Percentage of free space below which a warning is triggered.
.PARAMETER CsvPath
    Optional path to export the disk usage report as CSV.
.PARAMETER SmtpServer
    SMTP server to use when sending alert emails.
.PARAMETER From
    Sender address for alert emails.
.PARAMETER To
    Recipient address for alert emails.
.PARAMETER Subject
    Email subject used when sending alerts. Defaults to
    "Low Disk Space Alert".
.EXAMPLE
    PS> .\DiskUsageReport.ps1 -Volume C -AlertThreshold 15
    Checks the C drive and warns when it drops below 15% free space.
.EXAMPLE
    PS> .\DiskUsageReport.ps1 -Volume C,D -AlertThreshold 10 -CsvPath .\report.csv -SmtpServer smtp.example.com -From admin@example.com -To ops@example.com
    Generates a report for drives C and D, exports it to CSV and sends
    an email if any drive has less than 10% free space.
#>

[CmdletBinding()]
param(
    [string[]]$Volume,
    [int]$AlertThreshold = 20,
    [string]$CsvPath,
    [string]$SmtpServer,
    [string]$From,
    [string]$To,
    [string]$Subject = 'Low Disk Space Alert'
)

$drives = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DriveType=3"

if ($Volume) {
    $normalized = $Volume | ForEach-Object { $_.TrimEnd(':') }
    $drives = $drives | Where-Object { $normalized -contains $_.DeviceID.TrimEnd(':') }
}

$report = $drives | Select-Object DeviceID,
    @{Name="SizeGB";Expression={[math]::round($_.Size/1GB,2)}},
    @{Name="FreeGB";Expression={[math]::round($_.FreeSpace/1GB,2)}},
    @{Name="PercentFree";Expression={[math]::round(($_.FreeSpace/$_.Size)*100,2)}}

if ($CsvPath) {
    $report | Export-Csv -Path $CsvPath -NoTypeInformation
}

foreach ($entry in $report) {
    if ($entry.PercentFree -lt $AlertThreshold) {
        $message = "Drive $($entry.DeviceID) is below $AlertThreshold% free space ($($entry.PercentFree)% remaining)."
        Write-Warning $message
        if ($SmtpServer -and $From -and $To) {
            Send-MailMessage -SmtpServer $SmtpServer -From $From -To $To -Subject $Subject -Body $message
        }
    }
}

$report

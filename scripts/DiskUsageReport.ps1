<#
.SYNOPSIS
    Generates a disk usage report for local drives.
.DESCRIPTION
    Retrieves the total size, free space and percentage of free space for
    each fixed disk on the local computer.
.EXAMPLE
    PS> .\DiskUsageReport.ps1
    Generates a summary of disk usage for all local drives.
#>

Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3" |
    Select-Object DeviceID,
                  @{Name="SizeGB";Expression={[math]::round($_.Size/1GB,2)}},
                  @{Name="FreeGB";Expression={[math]::round($_.FreeSpace/1GB,2)}},
                  @{Name="PercentFree";Expression={[math]::round(($_.FreeSpace/$_.Size)*100,2)}}

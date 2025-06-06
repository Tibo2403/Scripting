<#
.SYNOPSIS
    Generates a disk usage report for local drives.
#>

Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3" |
    Select-Object DeviceID,
                  @{Name="SizeGB";Expression={[math]::round($_.Size/1GB,2)}},
                  @{Name="FreeGB";Expression={[math]::round($_.FreeSpace/1GB,2)}},
                  @{Name="PercentFree";Expression={[math]::round(($_.FreeSpace/$_.Size)*100,2)}}

<#
.SYNOPSIS
    Generates an inventory report for one or more computers.
.DESCRIPTION
    Collects basic system details using CIM/WMI from the specified computers. If
    no computer name is provided, the local computer is used.
.PARAMETER ComputerName
    Names of the computers to query. Defaults to the local computer.
.EXAMPLE
    PS> .\InventoryReport.ps1 -ComputerName srv01,srv02
    Displays a summary of inventory information for srv01 and srv02.
#>

[CmdletBinding()]
param(
    [string[]]$ComputerName = $env:COMPUTERNAME
)

foreach ($name in $ComputerName) {
    try {
        $os  = Get-CimInstance -ClassName Win32_OperatingSystem -ComputerName $name
        $cs  = Get-CimInstance -ClassName Win32_ComputerSystem -ComputerName $name
        $disks = Get-CimInstance -ClassName Win32_LogicalDisk -ComputerName $name -Filter "DriveType=3"

        $diskInfo = $disks | Select-Object DeviceID,
            @{Name='SizeGB';Expression={[math]::round($_.Size/1GB,2)}},
            @{Name='FreeGB';Expression={[math]::round($_.FreeSpace/1GB,2)}}

        [PSCustomObject]@{
            ComputerName = $name
            OSName       = $os.Caption
            OSVersion    = $os.Version
            MemoryGB     = [math]::round($cs.TotalPhysicalMemory/1GB,2)
            CPUs         = $cs.NumberOfLogicalProcessors
            Disks        = $diskInfo
        }
    } catch {
        Write-Error "Failed to gather inventory from $name. $_"
    }
}

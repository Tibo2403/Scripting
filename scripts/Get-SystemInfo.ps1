<#
.SYNOPSIS
    Displays basic system information for the local computer.
.DESCRIPTION
    Collects operating system details, memory information and processor count
    using Get-ComputerInfo.
.EXAMPLE
    PS> .\Get-SystemInfo.ps1
    Shows a brief summary of the current system.
#>

Get-ComputerInfo | Select-Object OSName, OSVersion, CsTotalPhysicalMemory, CsNumberOfLogicalProcessors, CsSystemType

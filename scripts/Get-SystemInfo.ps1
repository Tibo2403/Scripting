<#
.SYNOPSIS
    Displays basic system information for the local computer.
#>

Get-ComputerInfo | Select-Object OSName, OSVersion, CsTotalPhysicalMemory, CsNumberOfLogicalProcessors, CsSystemType

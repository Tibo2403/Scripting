<#
.SYNOPSIS
    Manages Hyper-V virtual machines.
.DESCRIPTION
    Allows creation, starting, stopping, removing or listing of virtual machines using Hyper-V.
.PARAMETER Action
    Action to perform: create, start, stop, remove or list.
.PARAMETER VMName
    Name of the virtual machine.
.PARAMETER MemoryStartupBytes
    Startup memory size when creating a VM (e.g. 2GB).
.PARAMETER VhdPath
    Path to the virtual hard disk when creating a VM.
.PARAMETER SwitchName
    Virtual switch used for network connectivity when creating a VM.
.EXAMPLE
    PS> .\VMManagement.ps1 -Action list
    Lists all virtual machines.
.EXAMPLE
    PS> .\VMManagement.ps1 -Action start -VMName Win10
    Starts the VM named 'Win10'.
.EXAMPLE
    PS> .\VMManagement.ps1 -Action create -VMName Test -MemoryStartupBytes 2GB -VhdPath C:\VMs\Test.vhdx -SwitchName vSwitch
    Creates a new VM called 'Test' with the specified settings.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('create','start','stop','remove','list')]
    [string]$Action,
    [string]$VMName,
    [string]$MemoryStartupBytes = '1GB',
    [string]$VhdPath,
    [string]$SwitchName
)

if (-not (Get-Module -ListAvailable -Name Hyper-V)) {
    Write-Error 'Hyper-V module is not installed. Please enable the Hyper-V feature.'
    return
}
Import-Module Hyper-V

switch ($Action.ToLower()) {
    'create' {
        if (-not $VMName -or -not $VhdPath -or -not $SwitchName) {
            Write-Error 'VMName, VhdPath and SwitchName are required to create a VM.'
            break
        }
        try {
            New-VM -Name $VMName -MemoryStartupBytes $MemoryStartupBytes -VHDPath $VhdPath -SwitchName $SwitchName -Generation 2 -ErrorAction Stop
            Write-Output "VM '$VMName' created."
        } catch {
            Write-Error "Failed to create VM '$VMName'. $_"
        }
    }
    'start' {
        if (-not $VMName) {
            Write-Error 'VMName is required to start a VM.'
            break
        }
        try {
            Start-VM -Name $VMName -ErrorAction Stop
        } catch {
            Write-Error "Failed to start VM '$VMName'. $_"
        }
    }
    'stop' {
        if (-not $VMName) {
            Write-Error 'VMName is required to stop a VM.'
            break
        }
        try {
            Stop-VM -Name $VMName -Force -ErrorAction Stop
        } catch {
            Write-Error "Failed to stop VM '$VMName'. $_"
        }
    }
    'remove' {
        if (-not $VMName) {
            Write-Error 'VMName is required to remove a VM.'
            break
        }
        try {
            Remove-VM -Name $VMName -Force -ErrorAction Stop
        } catch {
            Write-Error "Failed to remove VM '$VMName'. $_"
        }
    }
    'list' {
        try {
            Get-VM
        } catch {
            Write-Error "Failed to retrieve VMs. $_"
        }
    }
}

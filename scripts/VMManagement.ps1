<#
.SYNOPSIS
    Manages Hyper-V virtual machines or lists them.
.DESCRIPTION
    Allows starting, stopping, restarting or listing VMs using Hyper-V cmdlets.
.PARAMETER Action
    Operation to perform: start, stop, restart or list. Defaults to list.
.PARAMETER VMName
    Name of the VM to manage when using start, stop or restart.
.EXAMPLE
    PS> .\VMManagement.ps1 -Action list
    Lists all available virtual machines.
.EXAMPLE
    PS> .\VMManagement.ps1 -Action start -VMName "TestVM"
    Starts the virtual machine named 'TestVM'.
#>

param(
    [ValidateSet('start','stop','restart','list')]
    [string]$Action = 'list',
    [string]$VMName
)

if (-not (Get-Command Get-VM -ErrorAction SilentlyContinue)) {
    Write-Output 'Hyper-V module not available. Skipping.'
    return
}

switch ($Action.ToLower()) {
    'start' {
        if (-not $VMName) { Write-Error 'VMName is required for start.'; break }
        Start-VM -Name $VMName
    }
    'stop' {
        if (-not $VMName) { Write-Error 'VMName is required for stop.'; break }
        Stop-VM -Name $VMName -Force
    }
    'restart' {
        if (-not $VMName) { Write-Error 'VMName is required for restart.'; break }
        Restart-VM -Name $VMName
    }
    'list' {
        Get-VM
    }
}

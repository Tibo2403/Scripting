<#
.SYNOPSIS
    Displays detailed system information for the local computer.
.DESCRIPTION
    Collects operating system details, memory information and processor count
    using Get-ComputerInfo. Optional parameters allow inclusion of network
    adapter information, GPU details and basic health metrics. Results can be
    exported to CSV or JSON instead of being displayed on screen.
.PARAMETER IncludeNetwork
    Include network adapter information using Get-NetAdapter.
.PARAMETER IncludeGPU
    Include GPU information using Get-CimInstance Win32_VideoController.
.PARAMETER HealthStatus
    Include CPU temperature and usage statistics.
.PARAMETER OutCsv
    Export the collected information to '<OutputPath>.csv'.
.PARAMETER OutJson
    Export the collected information to '<OutputPath>.json'.
.PARAMETER OutputPath
    Base path for exported files. Defaults to 'SystemInfo' in the script directory.
.EXAMPLE
    PS> .\Get-SystemInfo.ps1 -IncludeNetwork -OutJson
    Writes system information including network adapters to SystemInfo.json.
.EXAMPLE
    PS> .\Get-SystemInfo.ps1 -IncludeGPU -HealthStatus -OutCsv
    Exports system information, GPU details and health metrics to SystemInfo.csv.
.EXAMPLE
    PS> .\Get-SystemInfo.ps1
    Displays a brief summary of the current system in the console.
.NOTES
    Uses Get-CimInstance for hardware queries and skips CPU temperature metrics
    when the required provider isn't available.
#>

[CmdletBinding()]
param(
    [switch]$IncludeNetwork,
    [switch]$IncludeGPU,
    [switch]$HealthStatus,
    [switch]$OutCsv,
    [switch]$OutJson,
    [ValidateScript({Test-Path (Split-Path $_)})]
    [string]$OutputPath = (Join-Path -Path $PSScriptRoot -ChildPath 'SystemInfo')
)

Get-Command Get-ComputerInfo -ErrorAction Stop
$sys = Get-ComputerInfo |
    Select-Object OSName, OSVersion, CsTotalPhysicalMemory,
                  CsNumberOfLogicalProcessors, CsSystemType

if ($IncludeNetwork) {
    Get-Command Get-NetAdapter -ErrorAction Stop
    $net = Get-NetAdapter |
        Select-Object Name, InterfaceDescription, Status, MacAddress
    $sys | Add-Member -MemberType NoteProperty -Name NetworkAdapters -Value $net
}

if ($IncludeGPU) {
    Get-Command Get-CimInstance -ErrorAction Stop
    $gpu = Get-CimInstance Win32_VideoController |
        Select-Object Name, DriverVersion
    $sys | Add-Member -MemberType NoteProperty -Name GPUs -Value $gpu
}

if ($HealthStatus) {
    Get-Command Get-CimInstance -ErrorAction Stop
    $cpuLoad = (Get-CimInstance Win32_Processor).LoadPercentage
    $tempObj = Get-CimInstance -Namespace root/wmi -Class MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | Select-Object -First 1
    $health = [pscustomobject]@{
        CpuLoadPercentage = $cpuLoad
    }
    if ($tempObj) {
        $tempC = [math]::Round(($tempObj.CurrentTemperature - 2732) / 10, 1)
        $health | Add-Member -MemberType NoteProperty -Name CpuTemperatureCelsius -Value $tempC
    }
    $sys | Add-Member -MemberType NoteProperty -Name HealthStatus -Value $health
}

if ($OutCsv) {
    $sys | ConvertTo-Csv -NoTypeInformation | Set-Content -Path "$OutputPath.csv"
}

if ($OutJson) {
    $sys | ConvertTo-Json -Depth 4 | Set-Content -Path "$OutputPath.json"
}

if (-not $OutCsv -and -not $OutJson) {
    $sys | Format-List *
}


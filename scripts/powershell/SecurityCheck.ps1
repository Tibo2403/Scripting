<#
.SYNOPSIS
    Performs a basic security audit of the local Windows system.
.DESCRIPTION
    Checks the status of Windows Firewall, antivirus (Windows Defender),
    the Windows Update service, BitLocker encryption, User Account Control,
    Remote Desktop configuration, SMBv1 and the latest installed hotfix.
    Results can optionally be saved to a JSON report file.
.PARAMETER ReportPath
    Optional path to save the audit results as JSON.
.EXAMPLE
    PS> .\SecurityCheck.ps1
    Shows the security status of the local computer.
.EXAMPLE
    PS> .\SecurityCheck.ps1 -ReportPath C:\report.json
    Saves the audit results to C:\report.json.
#>

[CmdletBinding()]
param(
    [string]$ReportPath
)

$results = [ordered]@{}

# Firewall status
try {
    $profiles = Get-NetFirewallProfile -ErrorAction Stop
    $results.Firewall = $profiles | Select-Object Name, Enabled
} catch {
    $results.Firewall = @{ Error = $_.Exception.Message }
}

# Antivirus (Windows Defender)
if (Get-Command Get-MpComputerStatus -ErrorAction SilentlyContinue) {
    try {
        $defender = Get-MpComputerStatus
        $results.Antivirus = @{
            RealTimeProtectionEnabled = $defender.RealTimeProtectionEnabled
            AntivirusEnabled          = $defender.AntivirusEnabled
            AntivirusSignatureAge     = $defender.AntivirusSignatureAge
        }
    } catch {
        $results.Antivirus = @{ Error = $_.Exception.Message }
    }
} else {
    $results.Antivirus = @{ Error = 'Get-MpComputerStatus not available.' }
}

# Windows Update service
try {
    $wu = Get-Service -Name wuauserv -ErrorAction Stop
    $results.WindowsUpdate = @{ Status = $wu.Status; StartType = $wu.StartType }
} catch {
    $results.WindowsUpdate = @{ Error = $_.Exception.Message }
}

# BitLocker status for system drive
if (Get-Command Get-BitLockerVolume -ErrorAction SilentlyContinue) {
    try {
        $blv = Get-BitLockerVolume -MountPoint $env:SystemDrive
        $results.BitLocker = @{ ProtectionStatus = $blv.ProtectionStatus; VolumeStatus = $blv.VolumeStatus }
    } catch {
        $results.BitLocker = @{ Error = $_.Exception.Message }
    }
} else {
    $results.BitLocker = @{ Error = 'Get-BitLockerVolume not available.' }
}

# User Account Control status
try {
    $uacReg = Get-ItemProperty -Path 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Policies\System' -Name EnableLUA -ErrorAction Stop
    $results.UAC = @{ Enabled = ($uacReg.EnableLUA -eq 1) }
} catch {
    $results.UAC = @{ Error = $_.Exception.Message }
}

# Remote Desktop setting
try {
    $rdpReg = Get-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections -ErrorAction Stop
    $results.RemoteDesktop = @{ Enabled = ($rdpReg.fDenyTSConnections -eq 0) }
} catch {
    $results.RemoteDesktop = @{ Error = $_.Exception.Message }
}

# SMBv1 feature state
if (Get-Command Get-WindowsOptionalFeature -ErrorAction SilentlyContinue) {
    try {
        $smb1 = Get-WindowsOptionalFeature -Online -FeatureName SMB1Protocol
        $results.SMBv1 = @{ State = $smb1.State }
    } catch {
        $results.SMBv1 = @{ Error = $_.Exception.Message }
    }
} else {
    $results.SMBv1 = @{ Error = 'Get-WindowsOptionalFeature not available.' }
}

# Latest installed hotfix
try {
    $hotfix = Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 1
    if ($hotfix) {
        $results.LastHotFix = @{ Id = $hotfix.HotFixID; InstalledOn = $hotfix.InstalledOn }
    } else {
        $results.LastHotFix = @{ Warning = 'No hotfix information found.' }
    }
} catch {
    $results.LastHotFix = @{ Error = $_.Exception.Message }
}

$results | Format-List

if ($ReportPath) {
    try {
        $results | ConvertTo-Json -Depth 3 | Out-File -FilePath $ReportPath -Encoding utf8
        Write-Output "Report saved to $ReportPath"
    } catch {
        Write-Error "Failed to save report to $ReportPath. $_"
    }
}

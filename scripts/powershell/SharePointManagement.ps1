<#
.SYNOPSIS
    Basic management for SharePoint On-Premise and SharePoint Online.
.DESCRIPTION
    Provides a unified interface for listing sites, creating a new site or adding an administrator.
    Automatically chooses the appropriate cmdlets depending on the mode.
.PARAMETER Mode
    Execution mode: OnPrem or Online.
.PARAMETER Action
    Operation to perform: ListSites, CreateSite or AddUser.
.PARAMETER SiteUrl
    URL of the target site collection.
.PARAMETER Credential
    Credentials for SharePoint connection.
.PARAMETER Template
    Site template used with CreateSite.
.PARAMETER UserLogin
    Login of the user for AddUser action.
.PARAMETER DisplayName
    Display name for the user (optional).
.PARAMETER Email
    Email of the user (optional).
.EXAMPLE
    .\SharePointManagement.ps1 -Mode Online -Action ListSites -Credential (Get-Credential)
.EXAMPLE
    .\SharePointManagement.ps1 -Mode OnPrem -Action CreateSite -SiteUrl "http://spserver/sites/test" -Template STS#0 -Credential (Get-Credential)
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('OnPrem','Online')]
    [string]$Mode,

    [Parameter(Mandatory)]
    [ValidateSet('ListSites','CreateSite','AddUser')]
    [string]$Action,

    [string]$SiteUrl,
    [PSCredential]$Credential,
    [string]$Template,
    [string]$UserLogin,
    [string]$DisplayName,
    [string]$Email
)

function Connect-SP {
    param(
        [string]$Mode,
        [string]$SiteUrl,
        [PSCredential]$Credential
    )

    if ($Mode -eq 'Online') {
        Write-Verbose 'Connecting to SharePoint Online...'
        Connect-SPOService -Url "https://$((New-Object System.Uri($SiteUrl)).Host)" -Credential $Credential
    } else {
        Write-Verbose 'Loading SharePoint On-Premise snap-in...'
        Add-PSSnapin Microsoft.SharePoint.PowerShell -ErrorAction SilentlyContinue
        $script:SPSite = Get-SPSite $SiteUrl
    }
}

function List-Sites {
    if ($Mode -eq 'Online') {
        Get-SPOSite | Select URL, Owner, Template
    } else {
        Get-SPSite -Limit All | Select URL, Owner, Template
    }
}

function Create-Site {
    param(
        [string]$SiteUrl,
        [string]$Template
    )

    if ($Mode -eq 'Online') {
        New-SPOSite -Url $SiteUrl -Owner $Credential.UserName -Template $Template -StorageQuota 1024
    } else {
        New-SPSite -Url $SiteUrl -OwnerAlias $Credential.UserName -Template $Template -Language 1036
    }
}

function Add-User {
    param(
        [string]$UserLogin,
        [string]$DisplayName,
        [string]$Email
    )

    if ($Mode -eq 'Online') {
        Set-SPOUser -Site $SiteUrl -LoginName $UserLogin -IsSiteCollectionAdmin $true
    } else {
        $web  = $SPSite.RootWeb
        $user = $web.EnsureUser($UserLogin)
        $user.Update()
    }
}

Connect-SP -Mode $Mode -SiteUrl $SiteUrl -Credential $Credential

switch ($Action) {
    'ListSites'  { List-Sites }
    'CreateSite' { Create-Site -SiteUrl $SiteUrl -Template $Template }
    'AddUser'    { Add-User -UserLogin $UserLogin -DisplayName $DisplayName -Email $Email }
}

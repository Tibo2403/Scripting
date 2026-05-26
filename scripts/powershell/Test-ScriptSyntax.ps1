[CmdletBinding()]
param(
    [string]$Path = "$PSScriptRoot",
    [switch]$WhatIf
)

$resolvedPath = Resolve-Path -LiteralPath $Path
$scriptExtensions = '.ps1', '.psm1', '.psd1'
$scripts = Get-ChildItem -LiteralPath $resolvedPath -Recurse -File |
    Where-Object { $_.Extension -in $scriptExtensions }
$hasErrors = $false

foreach ($script in $scripts) {
    if ($WhatIf) {
        Write-Host "Would parse $($script.FullName)"
        continue
    }

    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($script.FullName, [ref]$tokens, [ref]$errors) | Out-Null

    foreach ($errorRecord in $errors) {
        $hasErrors = $true
        Write-Error "$($script.FullName):$($errorRecord.Extent.StartLineNumber): $($errorRecord.Message)"
    }
}

if ($hasErrors) {
    exit 1
}

Write-Host "PowerShell syntax validation passed for $($scripts.Count) file(s)."

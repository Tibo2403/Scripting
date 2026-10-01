[CmdletBinding()]
param([Parameter(Mandatory)][string]$Path)
$ErrorActionPreference = 'Stop'
$results = @(Invoke-ScriptAnalyzer -Path $Path -Severity Error,Warning)
$results | Format-Table -AutoSize
if ($results.Count -gt 0) { exit 1 }

[CmdletBinding()]
param(
    [string]$Model = "hf.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF:latest",
    [switch]$SkipPull
)

$ErrorActionPreference = "Stop"

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    throw "Ollama is not installed or not available in PATH."
}

try {
    Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null
}
catch {
    Start-Process -WindowStyle Hidden -FilePath $ollama.Source -ArgumentList @("serve")
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        }
        catch {
            $ready = $false
        }
    }
    if (-not $ready) {
        throw "Ollama did not become ready on http://127.0.0.1:11434."
    }
}

$tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10
$modelNames = @($tags.models | ForEach-Object { $_.name })
if (($modelNames -notcontains $Model) -and (-not $SkipPull)) {
    & $ollama.Source pull $Model
    if ($LASTEXITCODE -ne 0) {
        throw "ollama pull failed for $Model"
    }
}

$tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10
$modelNames = @($tags.models | ForEach-Object { $_.name })
if ($modelNames -notcontains $Model) {
    throw "$Model is not installed. Run without -SkipPull to download it."
}

[pscustomobject]@{
    ok = $true
    model = $Model
    api_base = "http://127.0.0.1:11434/v1"
} | ConvertTo-Json

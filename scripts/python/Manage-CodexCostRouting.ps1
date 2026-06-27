[CmdletBinding()]
param(
    [ValidateSet('Run', 'Status', 'Stop')]
    [string]$Action = 'Run',
    [string]$CodexPath = 'codex',
    [int]$Port = 4000,
    [ValidateSet('LiteLLM', 'HuggingFace')]
    [string]$CodexProvider = 'LiteLLM'
)

$ErrorActionPreference = 'Stop'
$venvPath = 'C:\tmp\litellm-oss'
$litellmPath = Join-Path $venvPath 'Scripts\litellm.exe'
$pythonPath = Join-Path $venvPath 'Scripts\python.exe'
$configPath = Join-Path $PSScriptRoot 'litellm-cost-routing.yaml'
$routerPath = Join-Path $PSScriptRoot 'codex_cost_router.py'
$pidPath = Join-Path $env:TEMP 'codex-litellm-proxy.pid'
$stdoutPath = Join-Path $env:TEMP 'codex-litellm-proxy.out.log'
$stderrPath = Join-Path $env:TEMP 'codex-litellm-proxy.err.log'

function Get-PythonPath {
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) {
        return $bundled
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw 'Python 3.10+ est introuvable.'
}

function Test-ProxyPort {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connection = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $connection.AsyncWaitHandle.WaitOne(300)) {
            return $false
        }
        $client.EndConnect($connection)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Get-ProxyProcess {
    if (-not (Test-Path -LiteralPath $pidPath)) {
        return $null
    }

    $savedPid = Get-Content -LiteralPath $pidPath -Raw
    if ($savedPid -notmatch '^\s*\d+\s*$') {
        return $null
    }
    return Get-Process -Id ([int]$savedPid) -ErrorAction SilentlyContinue
}

function Remove-SessionSecrets {
    Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:HF_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:LITELLM_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue
}

function Remove-ProxyFiles {
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $stdoutPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue
}

function Install-LiteLLM {
    if (Test-Path -LiteralPath $litellmPath) {
        return
    }

    Write-Host "Installation locale de LiteLLM OSS dans $venvPath..."
    New-Item -ItemType Directory -Path (Split-Path -Parent $venvPath) -Force | Out-Null
    & (Get-PythonPath) -m venv $venvPath
    & $pythonPath -m pip install 'litellm[proxy]'
    if ($LASTEXITCODE -ne 0) {
        throw 'Echec de installation de LiteLLM OSS.'
    }
}

function Set-SessionSecrets {
    if (-not $env:OPENAI_API_KEY) {
        $secureKey = Read-Host 'OPENAI_API_KEY (saisie masquee, conservee uniquement en memoire)' -AsSecureString
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        try {
            $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        }
        finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        }
    }
    if (-not $env:OPENAI_API_KEY) {
        throw 'OPENAI_API_KEY est obligatoire.'
    }

    if (-not $env:GEMINI_API_KEY) {
        $secureKey = Read-Host 'GEMINI_API_KEY (optionnel, entree pour activer le dispatching Gemini)' -AsSecureString
        if ($secureKey.Length -gt 0) {
            $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
            try {
                $env:GEMINI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
            }
            finally {
                [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
            }
        }
    }

    if (-not $env:LITELLM_API_KEY) {
        $env:LITELLM_API_KEY = 'sk-local-' + [Guid]::NewGuid().ToString('N')
    }
    $env:PYTHONUTF8 = '1'
}

function Set-HuggingFaceSessionSecrets {
    if (-not $env:HF_TOKEN) {
        $secureKey = Read-Host 'HF_TOKEN (saisie masquee, conservee uniquement en memoire)' -AsSecureString
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        try {
            $env:HF_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        }
        finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        }
    }
    if (-not $env:HF_TOKEN) {
        throw 'HF_TOKEN est obligatoire pour le profil Hugging Face.'
    }

    $env:PYTHONUTF8 = '1'
}

function Stop-Router {
    $proxyProcess = Get-ProxyProcess
    if ($proxyProcess) {
        Stop-Process -Id $proxyProcess.Id -Force
        $proxyProcess.WaitForExit()
    }

    Remove-ProxyFiles
    & (Get-PythonPath) $routerPath disable | Out-Host
    Remove-SessionSecrets
}

function Start-Router {
    if (Test-ProxyPort) {
        throw "Le port $Port est deja utilise. Lancez '.\scripts\python\codex-cost-routing.cmd Stop' ou fermez le processus concerne."
    }

    Install-LiteLLM
    Set-SessionSecrets
    Remove-ProxyFiles

    Write-Host "Demarrage de LiteLLM OSS sur http://localhost:$Port..."
    $proxyProcess = Start-Process `
        -FilePath $litellmPath `
        -ArgumentList @('--config', $configPath, '--port', $Port) `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath
    Set-Content -LiteralPath $pidPath -Value $proxyProcess.Id -Encoding ascii

    try {
        foreach ($attempt in 1..120) {
            if ($proxyProcess.HasExited) {
                throw "LiteLLM s'est arrete pendant le demarrage. Consultez $stderrPath."
            }
            if (Test-ProxyPort) {
                & (Get-PythonPath) $routerPath enable | Out-Host
                if ($LASTEXITCODE -ne 0) {
                    throw 'Le profil Codex cost-routing ne peut pas etre active.'
                }
                return
            }
            Start-Sleep -Milliseconds 500
        }
        throw "LiteLLM n'a pas ouvert le port $Port. Consultez $stderrPath."
    }
    catch {
        Stop-Router
        throw
    }
}

function Show-Status {
    $proxyProcess = Get-ProxyProcess
    Write-Host 'Codex Cost Routing'
    Write-Host '------------------'
    if ($proxyProcess -and (Test-ProxyPort)) {
        Write-Host "LiteLLM OSS : actif (PID $($proxyProcess.Id), http://localhost:$Port)"
    }
    elseif (Test-ProxyPort) {
        Write-Host "Port $Port : occupe par un autre processus"
    }
    else {
        Write-Host 'LiteLLM OSS : arrete'
    }
    & (Get-PythonPath) $routerPath status
}

switch ($Action) {
    'Run' {
        if ($CodexProvider -eq 'HuggingFace') {
            Set-HuggingFaceSessionSecrets
            & (Get-PythonPath) $routerPath enable | Out-Host
            try {
                Write-Host 'Lancement de Codex avec le profil cost-routing-hf...'
                & $CodexPath --profile cost-routing-hf
            }
            finally {
                & (Get-PythonPath) $routerPath disable | Out-Host
                Remove-SessionSecrets
            }
        }
        else {
            Start-Router
            try {
                Write-Host 'Lancement de Codex avec le profil cost-routing...'
                & $CodexPath --profile cost-routing
            }
            finally {
                Stop-Router
            }
        }
    }
    'Status' {
        Show-Status
    }
    'Stop' {
        Stop-Router
        Write-Host 'LiteLLM OSS arrete et configuration Codex restauree.'
    }
}

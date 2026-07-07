[CmdletBinding()]
param(
    [ValidateSet('Run', 'Start', 'Status', 'Stop', 'Update')]
    [string]$Action = 'Run',
    [string]$CodexPath = 'codex',
    [int]$Port = 4000,
    [ValidateSet('Standard', 'LiteLLM', 'HuggingFace')]
    [string]$CodexProvider = 'Standard',
    [switch]$UpdateLiteLLM,
    [string]$LiteLLMVersion = '1.91.0'
)

$ErrorActionPreference = 'Stop'
$venvPath = 'C:\tmp\litellm-oss'
$litellmPath = Join-Path $venvPath 'Scripts\litellm.exe'
$pythonPath = Join-Path $venvPath 'Scripts\python.exe'
$configPath = Join-Path $PSScriptRoot 'litellm-cost-routing.yaml'
$routerPath = Join-Path $PSScriptRoot 'codex_cost_router.py'
$pidPath = Join-Path $env:TEMP 'codex-litellm-proxy.pid'
$apiKeyPath = Join-Path $env:TEMP 'codex-litellm-proxy.key'
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

function Test-OllamaQwen {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connection = $client.BeginConnect('127.0.0.1', 11434, $null, $null)
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
    Remove-Item -LiteralPath $apiKeyPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $stdoutPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue
}

function Get-LiteLLMVersion {
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        return $null
    }

    $showOutput = & $pythonPath -m pip show litellm 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }

    foreach ($line in $showOutput) {
        if ($line -match '^Version:\s*(.+)$') {
            return $Matches[1].Trim()
        }
    }

    return $null
}

function Install-LiteLLM {
    $forceUpdate = $UpdateLiteLLM -or ($Action -eq 'Update')
    if ((Test-Path -LiteralPath $litellmPath) -and (-not $forceUpdate)) {
        return
    }

    $venvHealthy = $false
    if (Test-Path -LiteralPath $pythonPath) {
        & $pythonPath -c "print('ok')" 1>$null 2>$null
        $venvHealthy = ($LASTEXITCODE -eq 0)
    }

    if (-not $venvHealthy) {
        if (Test-Path -LiteralPath $venvPath) {
            Write-Host "Recreation du venv LiteLLM OSS casse dans $venvPath..."
            Remove-Item -LiteralPath $venvPath -Recurse -Force
        }
        Write-Host "Installation locale de LiteLLM OSS dans $venvPath..."
        New-Item -ItemType Directory -Path (Split-Path -Parent $venvPath) -Force | Out-Null
        & (Get-PythonPath) -m venv $venvPath
        if ($LASTEXITCODE -ne 0) {
            throw 'Echec de creation du venv LiteLLM OSS.'
        }
    }
    elseif ($forceUpdate) {
        Write-Host "Mise a jour locale de LiteLLM OSS vers $LiteLLMVersion..."
    }

    $packageSpec = if ($LiteLLMVersion -eq 'latest') {
        'litellm[proxy]'
    }
    else {
        "litellm[proxy]==$LiteLLMVersion"
    }

    & $pythonPath -m pip install --upgrade $packageSpec
    if ($LASTEXITCODE -ne 0) {
        throw 'Echec de installation ou de mise a jour de LiteLLM OSS.'
    }

    $version = Get-LiteLLMVersion
    if ($version) {
        Write-Host "LiteLLM OSS version : $version"
    }
}

function Set-SessionSecrets {
    $qwenLocalAvailable = Test-OllamaQwen

    if (-not $env:OPENAI_API_KEY -and -not $qwenLocalAvailable) {
        $secureKey = Read-Host 'OPENAI_API_KEY (optionnel, entree pour ignorer)' -AsSecureString
        if ($secureKey.Length -gt 0) {
            $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
            try {
                $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
            }
            finally {
                [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
            }
        }
    }

    if (-not $env:GEMINI_API_KEY -and -not $qwenLocalAvailable) {
        $secureKey = Read-Host 'GEMINI_API_KEY (optionnel, entree pour ignorer)' -AsSecureString
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

    if (-not $env:OPENAI_API_KEY -and -not $env:GEMINI_API_KEY -and -not $qwenLocalAvailable) {
        throw 'LiteLLM a besoin au moins de OPENAI_API_KEY, GEMINI_API_KEY ou Qwen local sur Ollama.'
    }

    if (-not $env:LITELLM_API_KEY) {
        $env:LITELLM_API_KEY = 'sk-local-' + [Guid]::NewGuid().ToString('N')
    }
    Set-Content -LiteralPath $apiKeyPath -Value $env:LITELLM_API_KEY -Encoding ascii
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
    if ($CodexProvider -eq 'Standard') {
        Write-Host 'Chemin Codex standard: aucun proxy LiteLLM a demarrer.'
        return
    }

    if (Test-ProxyPort) {
        throw "Le port $Port est deja utilise. Lancez '.\scripts\python\codex-cost-routing.cmd Stop' ou fermez le processus concerne."
    }

    Install-LiteLLM
    Remove-ProxyFiles
    Set-SessionSecrets

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
    $litellmVersion = Get-LiteLLMVersion
    if ($litellmVersion) {
        Write-Host "LiteLLM version : $litellmVersion"
    }
    else {
        Write-Host 'LiteLLM version : non installe'
    }
    & (Get-PythonPath) $routerPath status
}

switch ($Action) {
    'Run' {
        if ($CodexProvider -eq 'Standard') {
            Write-Host 'Lancement de Codex par le chemin standard.'
            Write-Host "LiteLLM actif : $(if (Test-ProxyPort) { 'oui' } else { 'non' })"
            Write-Host "Qwen local : $(if (Test-OllamaQwen) { 'oui' } else { 'non' })"
            & $CodexPath
        }
        elseif ($CodexProvider -eq 'HuggingFace') {
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
                Write-Host 'Gemini peut etre utilise par LiteLLM si GEMINI_API_KEY est configuree.'
                Write-Host "Qwen local : $(if (Test-OllamaQwen) { 'disponible via Ollama' } else { 'indisponible' })"
                & $CodexPath --profile cost-routing
            }
            finally {
                Stop-Router
            }
        }
    }
    'Start' {
        if ($CodexProvider -eq 'Standard') {
            Write-Host 'Chemin Codex standard: rien a activer.'
            Write-Host 'Utilisez -CodexProvider LiteLLM pour activer le proxy Gemini/Qwen.'
        }
        elseif ($CodexProvider -eq 'HuggingFace') {
            Set-HuggingFaceSessionSecrets
            & (Get-PythonPath) $routerPath enable | Out-Host
            Write-Host 'Profil cost-routing-hf active.'
            Write-Host 'Lancez Codex avec: codex --profile cost-routing-hf'
            Write-Host "Arret: .\scripts\python\Manage-CodexCostRouting.ps1 -Action Stop"
        }
        else {
            Start-Router
            Write-Host 'LiteLLM OSS actif et profil cost-routing active.'
            Write-Host "Endpoint: http://localhost:$Port/v1"
            Write-Host 'Lancez Codex avec: codex --profile cost-routing'
            Write-Host "Arret: .\scripts\python\Manage-CodexCostRouting.ps1 -Action Stop"
        }
    }
    'Status' {
        Show-Status
    }
    'Update' {
        Install-LiteLLM
        Show-Status
    }
    'Stop' {
        Stop-Router
        Write-Host 'LiteLLM OSS arrete et configuration Codex restauree.'
    }
}

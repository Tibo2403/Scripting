<#
.SYNOPSIS
    Crawls a website to verify the status of internal and external links.
.DESCRIPTION
    Recursively follows links starting from the specified URL, up to a configurable depth.
    Each link is requested using Invoke-WebRequest and the results are exported to a CSV file.
    Optionally generates an HTML report and sends notifications when broken links are detected.
.PARAMETER BaseUrl
    Root URL to start crawling from. This parameter is mandatory.
.PARAMETER CsvPath
    Path to the CSV output file.
.PARAMETER MaxDepth
    Maximum recursion depth when following links. Default is 3.
.PARAMETER ContentTypes
    Types of content to include: html, image, document or all.
.PARAMETER HtmlReportPath
    Optional path to save an HTML report.
.PARAMETER NotifyEmail
    Optional email address to notify if broken links are found.
.PARAMETER SmtpServer
    SMTP server to use when sending notification emails.
.PARAMETER SmtpPort
    Port number of the SMTP server. Defaults to 25.
.PARAMETER Credential
    Credentials for authenticating to the SMTP server.
.PARAMETER UseSsl
    Use SSL/TLS when connecting to the SMTP server.
.PARAMETER ToastNotify
    Display a toast notification when broken links are detected.
.PARAMETER MaxJobs
    Maximum number of concurrent jobs when testing external links. Default is 10.
.EXAMPLE
    PS> .\LinkCrawler.ps1 -BaseUrl "https://example.com" -MaxDepth 2 -ContentTypes html,image -HtmlReportPath report.html
.EXAMPLE
    PS> .\LinkCrawler.ps1 -BaseUrl "https://example.com" -NotifyEmail admin@example.com
.NOTES
    Parallel execution requires PowerShell 7 or the ThreadJob module; otherwise URLs are tested sequentially.
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory=$true)]
    [string]$BaseUrl,
    [string]$CsvPath = "./liens_verifies.csv",
    [int]$MaxDepth = 3,
    [ValidateSet('html','image','document','all')]
    [string[]]$ContentTypes = @('html'),
    [string]$HtmlReportPath,
    [string]$NotifyEmail,
    [string]$SmtpServer,
    [int]$SmtpPort = 25,
    [pscredential]$Credential,
    [switch]$UseSsl,
    [switch]$ToastNotify,
    [int]$MaxJobs = 10
)

$visitedUrls = @{}
$results = @()

$threadJobAvailable = [bool](Get-Module -ListAvailable -Name ThreadJob)

$HtmlExt  = @('.html','.htm','/')
$ImageExt = @('.jpg','.jpeg','.png','.gif','.bmp','.svg','.webp')
$DocExt   = @('.pdf','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.txt','.rtf')

function Should-IncludeLink {
    param([string]$link)
    if ($ContentTypes -contains 'all') { return $true }
    $ext = [System.IO.Path]::GetExtension($link).ToLower()
    if ([string]::IsNullOrWhiteSpace($ext)) { $ext = '/' }
    if ('html' -in $ContentTypes -and $HtmlExt -contains $ext) { return $true }
    if ('image' -in $ContentTypes -and $ImageExt -contains $ext) { return $true }
    if ('document' -in $ContentTypes -and $DocExt -contains $ext) { return $true }
    return $false
}

function Get-LinksFromPage {
    param (
        [string]$url,
        [string]$baseUrl
    )

    $links = @()

    $response = Invoke-WebRequest -Uri $url -TimeoutSec 10 -ErrorAction Stop

    if ([Type]::GetType('HtmlAgilityPack.HtmlDocument')) {
        $doc = [HtmlAgilityPack.HtmlDocument]::new()
        $doc.LoadHtml($response.Content)
        $nodes = $doc.DocumentNode.SelectNodes('//a[@href]')
        if ($nodes) {
            foreach ($node in $nodes) {
                $href = $node.GetAttributeValue('href','')
                if ($href -like 'http*') {
                    $links += $href
                } elseif ($href.StartsWith('/')) {
                    $links += "$baseUrl$href"
                }
            }
        }
    } else {
        foreach ($link in $response.Links) {
            $href = $link.href
            if ($href -like 'http*') {
                $links += $href
            } elseif ($href.StartsWith('/')) {
                $links += "$baseUrl$href"
            }
        }
    }

    return $links | Sort-Object -Unique | Where-Object { Should-IncludeLink $_ }
}

function Test-Url {
    param (
        [string]$url
    )

    try {
        $response = Invoke-WebRequest -Uri $url -Method Head -TimeoutSec 10 -ErrorAction Stop
        return @{ Url = $url; Status = 'OK'; Code = $response.StatusCode; Message = '' }
    } catch {
        $code = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 'NA' }
        return @{ Url = $url; Status = 'ERROR'; Code = $code; Message = $_.Exception.Message }
    }
}

function Test-UrlsParallel {
    param([string[]]$urls)
    if (-not $urls) { return @() }
    if (-not $threadJobAvailable) {
        return $urls | ForEach-Object { [pscustomobject](Test-Url -url $_) }
    }
    $jobs = @()
    foreach ($u in $urls) {
        while ((Get-Job -State Running).Count -ge $MaxJobs) { Start-Sleep -Seconds 1 }
        $jobs += Start-ThreadJob -ScriptBlock {
            param($link)
            try {
                $r = Invoke-WebRequest -Uri $link -Method Head -TimeoutSec 10 -ErrorAction Stop
                [pscustomobject]@{ Url = $link; Status = 'OK'; Code = $r.StatusCode; Message = '' }
            } catch {
                $c = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 'NA' }
                [pscustomobject]@{ Url = $link; Status = 'ERROR'; Code = $c; Message = $_.Exception.Message }
            }
        } -ArgumentList $u
    }
    Wait-Job $jobs | Out-Null
    $res = $jobs | Receive-Job
    $jobs | Remove-Job
    return $res
}

function Crawl {
    param (
        [string]$url,
        [int]$depth
    )

    if ($visitedUrls.ContainsKey($url) -or $depth -gt $MaxDepth) { return }
    $visitedUrls[$url] = $true

    try {
        $links = Get-LinksFromPage -url $url -baseUrl $BaseUrl
        $result = Test-Url -url $url
        $results += [pscustomobject]$result
        $external = @()
        foreach ($link in $links) {
            if ($link.StartsWith($BaseUrl)) {
                Crawl -url $link -depth ($depth + 1)
            } else {
                $external += $link
            }
        }
        if ($external.Count -gt 0) {
            $results += Test-UrlsParallel -urls $external
        }
    } catch {
        $code = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 'NA' }
        $results += [pscustomobject]@{ Url = $url; Status = 'ERROR'; Code = $code; Message = $_.Exception.Message }
    }
}

function Generate-HtmlReport {
    param([object[]]$data,[string]$path)
    $rows = foreach ($r in $data) {
        $cls = if ($r.Status -eq 'OK') { 'success' } else { 'error' }
        "<tr class='$cls'><td>$($r.Url)</td><td>$($r.Status)</td><td>$($r.Code)</td><td>$($r.Message)</td></tr>"
    }
    $html = @"
<html>
<head>
<style>
body{font-family:Arial;font-size:12px}
.success{color:green}
.error{color:red}
</style>
</head>
<body>
<h1>Link Report for $BaseUrl</h1>
<table border='1' cellpadding='4' cellspacing='0'>
<tr><th>URL</th><th>Status</th><th>Code</th><th>Message</th></tr>
$($rows -join "`n")
</table>
</body>
</html>
"@
    $html | Set-Content -Path $path -Encoding UTF8
    Write-Host "📄 HTML report generated at $path" -ForegroundColor Green
}

function Send-Notifications {
    param([object[]]$errors)
    if (-not $errors) { return }
    if ($NotifyEmail -and $SmtpServer) {
        $body = $errors | Format-Table Url,Code,Message -AutoSize | Out-String
        try {
            $mail = [System.Net.Mail.MailMessage]::new($NotifyEmail, $NotifyEmail, 'Broken Links', $body)
            $smtp = [System.Net.Mail.SmtpClient]::new($SmtpServer, $SmtpPort)
            if ($UseSsl) { $smtp.EnableSsl = $true }
            if ($Credential) { $smtp.Credentials = $Credential.GetNetworkCredential() }
            $smtp.Send($mail)
        } catch {
            Write-Warning "Failed to send email notification: $_"
        } finally {
            if ($null -ne $mail) { $mail.Dispose() }
            if ($null -ne $smtp) { $smtp.Dispose() }
        }
    }
    if ($ToastNotify) {
        if (Get-Module -ListAvailable -Name BurntToast) {
            Import-Module BurntToast -ErrorAction SilentlyContinue
            New-BurntToastNotification -Text 'LinkCrawler', "$($errors.Count) broken links detected."
        } else {
            Write-Warning 'BurntToast module is not installed.'
        }
    }
}

Write-Host "Début du scan récursif de $BaseUrl (profondeur max : $MaxDepth)" -ForegroundColor Cyan
Crawl -url $BaseUrl -depth 0

$results | Sort-Object Url -Unique | Export-Csv -Path $CsvPath -NoTypeInformation -Encoding UTF8
Write-Host "✅ Résultats exportés dans $CsvPath" -ForegroundColor Green

if ($HtmlReportPath) { Generate-HtmlReport -data $results -path $HtmlReportPath }
$broken = $results | Where-Object Status -eq 'ERROR'
if ($broken.Count -gt 0) { Send-Notifications -errors $broken }

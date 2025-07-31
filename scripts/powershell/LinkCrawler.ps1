<#
.SYNOPSIS
    Crawls a website to verify the status of internal and external links.
.DESCRIPTION
    Recursively follows links starting from the specified URL, up to a configurable depth.
    Each link is requested using Invoke-WebRequest and the results are exported to a CSV file.
    Optionally generates an HTML report and sends notifications when broken links are detected.
.PARAMETER BaseUrl
    Root URL to start crawling from.
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
.PARAMETER ToastNotify
    Display a toast notification when broken links are detected.
.EXAMPLE
    PS> .\LinkCrawler.ps1 -BaseUrl "https://example.com" -MaxDepth 2 -ContentTypes html,image -HtmlReportPath report.html
.EXAMPLE
    PS> .\LinkCrawler.ps1 -BaseUrl "https://example.com" -NotifyEmail admin@example.com
#>

[CmdletBinding()]
param (
    [string]$BaseUrl = "https://exemple.com",
    [string]$CsvPath = "./liens_verifies.csv",
    [int]$MaxDepth = 3,
    [ValidateSet('html','image','document','all')]
    [string[]]$ContentTypes = @('html'),
    [string]$HtmlReportPath,
    [string]$NotifyEmail,
    [switch]$ToastNotify
)

$visitedUrls = @{}
$results = @()

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
        [string]$htmlContent,
        [string]$baseUrl
    )

    $matches = Select-String -InputObject $htmlContent -Pattern 'href="(.*?)"' -AllMatches
    $links = @()

    foreach ($match in $matches.Matches) {
        $href = $match.Groups[1].Value
        if ($href -like "http*") {
            $links += $href
        } elseif ($href -like "/*") {
            $links += "$baseUrl$href"
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
    $jobs = @()
    foreach ($u in $urls) {
        $jobs += Start-Job -ScriptBlock {
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
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
        $result = Test-Url -url $url
        $results += [pscustomobject]$result

        $links = Get-LinksFromPage -htmlContent $response.Content -baseUrl $BaseUrl
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
    if ($NotifyEmail) {
        $body = $errors | Format-Table Url,Code,Message -AutoSize | Out-String
        try {
            Send-MailMessage -To $NotifyEmail -From $NotifyEmail -Subject "Broken Links" -Body $body -SmtpServer 'localhost'
        } catch {
            Write-Warning "Failed to send email notification: $_"
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

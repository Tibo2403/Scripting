<#
.SYNOPSIS
    Crawls a website to verify the status of internal and external links.
.DESCRIPTION
    Recursively follows links starting from the specified URL, up to a
    configurable depth. Each link is requested using Invoke-WebRequest and
    the results are exported to a CSV file.
.PARAMETER BaseUrl
    Root URL to start crawling from.
.PARAMETER CsvPath
    Path to the CSV output file.
.PARAMETER MaxDepth
    Maximum recursion depth when following links. Default is 3.
.EXAMPLE
    PS> .\LinkCrawler.ps1 -BaseUrl "https://example.com" -MaxDepth 2
#>

[CmdletBinding()]
param (
    [string]$BaseUrl = "https://exemple.com",
    [string]$CsvPath = ".\liens_verifies.csv",
    [int]$MaxDepth = 3
)

$visitedUrls = @{}
$results = @()

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

    return $links | Sort-Object -Unique
}

function Test-Url {
    param (
        [string]$url
    )

    try {
        $response = Invoke-WebRequest -Uri $url -Method Head -TimeoutSec 10 -ErrorAction Stop
        return @{
            Url = $url
            Status = "OK"
            Code = $response.StatusCode
        }
    } catch {
        return @{
            Url = $url
            Status = "ERROR"
            Code = $_.Exception.Response.StatusCode.value__
        }
    }
}

function Crawl {
    param (
        [string]$url,
        [int]$depth
    )

    if ($visitedUrls.ContainsKey($url) -or $depth -gt $MaxDepth) {
        return
    }

    $visitedUrls[$url] = $true

    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
        $result = Test-Url -url $url
        $results += [pscustomobject]$result

        $links = Get-LinksFromPage -htmlContent $response.Content -baseUrl $BaseUrl

        foreach ($link in $links) {
            if ($link.StartsWith($BaseUrl)) {
                Crawl -url $link -depth ($depth + 1)
            } else {
                $extResult = Test-Url -url $link
                $results += [pscustomobject]$extResult
            }
        }

    } catch {
        $results += [pscustomobject]@{
            Url = $url
            Status = "ERROR"
            Code = "NA"
        }
    }
}

Write-Host "Début du scan récursif de $BaseUrl (profondeur max : $MaxDepth)" -ForegroundColor Cyan
Crawl -url $BaseUrl -depth 0

$results | Sort-Object Url -Unique | Export-Csv -Path $CsvPath -NoTypeInformation -Encoding UTF8
Write-Host "✅ Résultats exportés dans $CsvPath" -ForegroundColor Green

param([string]$Phase = 'manual', [int]$Samples = 5)
$ErrorActionPreference = 'Stop'
$checks = @()
for ($index = 0; $index -lt $Samples; $index++) {
    foreach ($port in @(18080, 18888)) {
        $url = "http://localhost:$port/"
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 10
            $expected = if ($port -eq 18080) { 'name="vote"' } else { 'statsCtrl' }
            $checks += [pscustomobject]@{
                Utc = [DateTime]::UtcNow.ToString('o'); Url = $url
                Status = [int]$response.StatusCode; ExpectedContent = $response.Content.Contains($expected)
            }
        } catch {
            $checks += [pscustomobject]@{
                Utc = [DateTime]::UtcNow.ToString('o'); Url = $url
                Status = 0; ExpectedContent = $false; Error = $_.Exception.Message
            }
        }
    }
    if ($index -lt $Samples - 1) { Start-Sleep -Seconds 1 }
}
$destination = Join-Path $PSScriptRoot "../docs/proofs/$Phase-windows-http.json"
$checks | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -LiteralPath $destination
$checks | Format-Table Utc,Url,Status,ExpectedContent
if ($checks | Where-Object { $_.Status -ne 200 -or -not $_.ExpectedContent }) {
    throw 'Au moins une vérification HTTP a échoué ; voir le fichier de preuves.'
}

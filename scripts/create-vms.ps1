$ErrorActionPreference = 'Stop'
$mp = 'C:\Program Files\Multipass\bin\multipass.exe'
if (-not (Test-Path -LiteralPath $mp)) { throw 'Installer Multipass avant ce script.' }
$cloudInit = Join-Path $PSScriptRoot 'cloud-init.yaml'
$inventory = & $mp list --format json
if ($LASTEXITCODE -ne 0) { throw 'Multipass inaccessible : résoudre la connexion au service avant création.' }
$existing = ($inventory | ConvertFrom-Json).list.name
foreach ($spec in @(
    @{Name='supinfo-manager'; Memory='4G'; Disk='25G'},
    @{Name='supinfo-worker1'; Memory='2G'; Disk='20G'},
    @{Name='supinfo-worker2'; Memory='2G'; Disk='20G'}
)) {
    if ($existing -contains $spec.Name) {
        Write-Host "$($spec.Name) existe déjà : conservée."
        continue
    }
    & $mp launch 24.04 --name $spec.Name --cpus 2 --memory $spec.Memory --disk $spec.Disk --cloud-init $cloudInit
    if ($LASTEXITCODE -ne 0) { throw "Échec de création : $($spec.Name)" }
}
& $mp list

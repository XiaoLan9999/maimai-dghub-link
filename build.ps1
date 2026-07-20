param(
    [Parameter(Mandatory = $true)]
    [string]$GamePackage
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$csc = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
$assemblyCSharp = Join-Path $GamePackage "Sinmai_Data\Managed\Assembly-CSharp.dll"
$melonLoader = Join-Path $GamePackage "MelonLoader\net35\MelonLoader.dll"
$harmony = Join-Path $GamePackage "MelonLoader\net35\0Harmony.dll"
$manifestPath = Join-Path $root "plugin\manifest.json"
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$version = [string]$manifest.version
$dist = [IO.Path]::GetFullPath((Join-Path $root "dist"))
$gameMod = Join-Path $dist "game-mod"
$pluginStage = Join-Path $dist "plugin-stage"
$bridgeDll = Join-Path $gameMod "MaiDGBridge.dll"

if (-not $dist.StartsWith(([IO.Path]::GetFullPath($root) + [IO.Path]::DirectorySeparatorChar), [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to use a dist path outside the project: $dist"
}

foreach ($path in @($csc, $assemblyCSharp, $melonLoader, $harmony)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required file not found: $path"
    }
}

if (Test-Path -LiteralPath $dist) {
    Remove-Item -LiteralPath $dist -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $gameMod, $pluginStage | Out-Null

& $csc /nologo /target:library /optimize+ /warn:4 `
    /out:$bridgeDll `
    /reference:$melonLoader `
    /reference:$harmony `
    /reference:$assemblyCSharp `
    (Join-Path $root "bridge\MaiDGBridge.cs")
if ($LASTEXITCODE -ne 0) {
    throw "C# compilation failed"
}

Copy-Item -LiteralPath (Join-Path $root "bridge\MaiDGBridge.ini") -Destination $gameMod
Copy-Item -LiteralPath (Join-Path $root "plugin\main.py") -Destination $pluginStage
Copy-Item -LiteralPath (Join-Path $root "plugin\installer.py") -Destination $pluginStage
Copy-Item -LiteralPath (Join-Path $root "plugin\vrchat_osc.py") -Destination $pluginStage
Copy-Item -LiteralPath (Join-Path $root "plugin\SOURCE.md") -Destination $pluginStage
Copy-Item -LiteralPath $manifestPath -Destination $pluginStage
Copy-Item -LiteralPath (Join-Path $root "LICENSE") -Destination $pluginStage

$payloadStage = Join-Path $pluginStage "payload"
New-Item -ItemType Directory -Force -Path $payloadStage | Out-Null
Copy-Item -LiteralPath $bridgeDll -Destination $payloadStage
Copy-Item -LiteralPath (Join-Path $root "bridge\MaiDGBridge.ini") -Destination $payloadStage

$bridgeHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $bridgeDll).Hash.ToLowerInvariant()
$descriptor = [ordered]@{
    plugin_version = $version
    bridge_version = $version
    sha256 = $bridgeHash
}
$descriptorJson = $descriptor | ConvertTo-Json
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText((Join-Path $payloadStage "bridge.json"), $descriptorJson + "`n", $utf8NoBom)

$pluginZip = Join-Path $dist "maimai_link-$version.zip"
Compress-Archive -Path (Join-Path $pluginStage "*") -DestinationPath $pluginZip
Remove-Item -LiteralPath $pluginStage -Recurse -Force
Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination $dist

Write-Output "Built: $pluginZip"
Write-Output "Built: $gameMod"

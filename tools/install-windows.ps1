# 造世界｜主世界地图 一键安装（Windows / PowerShell）
# 作用：把工程复制进编辑器目录，并在 projects.json 里登记

$ErrorActionPreference = 'Stop'

$Name   = 'project_vqo1bvzh'
$Root   = Split-Path -Parent $PSScriptRoot
$Src    = Join-Path $Root "projects\$Name"
$AppDir = Join-Path $env:APPDATA 'AI World Creator'
$Dest   = Join-Path $AppDir 'projects'
$Stamp  = Get-Date -Format 'yyyyMMddHHmmss'

Write-Host '======================================'
Write-Host '  造世界｜主世界地图 安装程序（Windows）'
Write-Host '======================================'
Write-Host ''

if (-not (Test-Path $Src)) {
    Write-Host "❌ 找不到工程文件夹：$Src" -ForegroundColor Red
    Write-Host '   请把整个压缩包解压后再运行本脚本。'
    Read-Host '按回车键退出'
    exit 1
}

if (-not (Test-Path $AppDir)) {
    Write-Host "⚠️  没找到造世界编辑器的数据目录：" -ForegroundColor Yellow
    Write-Host "   $AppDir"
    Write-Host '   请先打开一次造世界编辑器并登录，退出后再运行本脚本。'
    Read-Host '按回车键退出'
    exit 1
}

New-Item -ItemType Directory -Force -Path $Dest | Out-Null

$Target = Join-Path $Dest $Name
if (Test-Path $Target) {
    Rename-Item -Path $Target -NewName "$Name.bak-$Stamp"
    Write-Host "ℹ️  已存在的同名工程已备份为：$Name.bak-$Stamp"
}

Copy-Item -Path $Src -Destination $Target -Recurse -Force
Write-Host "✅ 工程已复制到：$Target"

$jsonPath = Join-Path $Dest 'projects.json'
$list = @()
if (Test-Path $jsonPath) {
    Copy-Item $jsonPath "$jsonPath.bak-$Stamp"
    Write-Host 'ℹ️  已备份原 projects.json'
    $raw = Get-Content $jsonPath -Raw -Encoding UTF8
    if ($raw -and $raw.Trim()) {
        try {
            $parsed = $raw | ConvertFrom-Json
            if ($null -ne $parsed) { $list = @($parsed) }
        } catch {
            Write-Host '⚠️  原有 projects.json 解析失败，将新建一份' -ForegroundColor Yellow
        }
    }
}

# 优先沿用接收者自己的账号 uid
$uid = '3309980302973310'
foreach ($e in $list) {
    if ($e.uid) { $uid = [string]$e.uid; break }
}

$now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$list = @($list | Where-Object { $_.projectPath -ne $Target })
$list += [pscustomobject]@{
    projectPath     = $Target
    latestOpenTime  = $now
    latestEditTime  = $now
    uid             = $uid
}

$jsonText = ConvertTo-Json -InputObject @($list) -Depth 5
if (-not $jsonText.TrimStart().StartsWith('[')) { $jsonText = "[$jsonText]" }
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($jsonPath, $jsonText, $utf8)

Write-Host '✅ 已在 projects.json 里登记'
Write-Host ''
Write-Host '🎉 安装完成！' -ForegroundColor Green
Write-Host '   现在重新打开造世界编辑器，在项目列表里点「糖果童趣小镇（主世界）」即可。'
Write-Host ''
Read-Host '按回车键关闭这个窗口'

param(
    [Parameter(Mandatory=$true)][string]$Ip,
    [string]$Client = '',
    [switch]$Force,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$expected = '2dca9b1e122e21363e14eeeb2372598c773205a907ed8d2b2d54a7229ad6ba18'

function Resolve-Client([string]$path) {
    if ($path) {
        if (Test-Path (Join-Path $path 'Europa_Client.exe')) { return (Resolve-Path $path).Path }
        throw "指定的目录里没有 Europa_Client.exe：$path"
    }
    $saved = Join-Path $PSScriptRoot 'client-path.txt'
    if (Test-Path $saved) {
        $candidate = (Get-Content $saved -Raw).Trim()
        if ($candidate -and (Test-Path (Join-Path $candidate 'Europa_Client.exe'))) { return $candidate }
    }
    Write-Host '请把本工具放进「Ring of Elysium」游戏目录（与 Europa_Client.exe 同级），' -ForegroundColor Yellow
    Write-Host '或者现在输入游戏目录的完整路径：' -ForegroundColor Yellow
    $inputPath = (Read-Host).Trim().Trim('"')
    if (-not (Test-Path (Join-Path $inputPath 'Europa_Client.exe'))) {
        throw "这个目录里没有 Europa_Client.exe：$inputPath"
    }
    Set-Content -LiteralPath $saved -Value $inputPath -Encoding ASCII
    return (Resolve-Path $inputPath).Path
}

$clientDir = Resolve-Client $Client
$exe = Join-Path $clientDir 'Europa_Client.exe'
Write-Host "客户端目录: $clientDir"

Write-Host '校验客户端版本（2022 / 0.2.989.0）...'
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne $expected) {
    if (-not $Force) {
        Write-Host '客户端版本不匹配：' -ForegroundColor Red
        Write-Host "  期望 $expected" -ForegroundColor Red
        Write-Host "  实际 $hash" -ForegroundColor Red
        Write-Host '需要 2022 版（0.2.989.0）完整客户端。确定要继续请加 -Force。' -ForegroundColor Red
        exit 2
    }
    Write-Host '版本不一致，但已指定 -Force，继续启动。' -ForegroundColor Yellow
}

foreach ($name in @('ProtocalHandler_x64.dll','Tenproxy64.dll','SFC\World_EU_ICELAND_4096_RemainingFiles.sfc')) {
    if (-not (Test-Path (Join-Path $clientDir $name))) {
        Write-Host "警告：缺少 $name（可能进不去图）" -ForegroundColor Yellow
    }
}

$gameArgs = @('-language=en','-garena','-uid=1',("-server=$Ip`:8001"))
Write-Host ("启动: Europa_Client.exe " + ($gameArgs -join ' ')) -ForegroundColor Green
if ($DryRun) { Write-Host 'DryRun: 不启动游戏。'; exit 0 }
$proc = Start-Process -FilePath $exe -ArgumentList $gameArgs -WorkingDirectory $clientDir -PassThru
Write-Host "已启动，PID $($proc.Id)。进游戏后：Esc 关活动中心 → Play → 训练/开始配对。"
exit 0

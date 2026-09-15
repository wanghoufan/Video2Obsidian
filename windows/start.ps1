# 懒得笔记｜Windows 11 一键启动（PowerShell）
#   双击 start.bat 或在 PowerShell 里执行：.\start.ps1
#   换端口：$env:V2O_PORT=8900; .\start.ps1
#
# 端口真源只有 app/server.py 的 PORT 默认值；本脚本只做「V2O_PORT 覆盖」这一处
# 透传，默认端口与 URL 一律由 $Port / $Url 变量派生，不另写第二份端口号。

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $Root

# ---- 端口单点：V2O_PORT 优先，否则用 app/server.py 的 PORT 默认值 --------
$Port = if ($env:V2O_PORT) { $env:V2O_PORT } else { "8899" }
$Url  = "http://127.0.0.1:$Port/"

# ---- 1. venv（官方 Python 3.12）----
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "未找到 .venv，正在用 Python 3.12 创建…"
    py -3.12 -m venv .venv
    if (-not (Test-Path $VenvPython)) {
        Write-Host "创建虚拟环境失败：请确认已安装官方 64-bit Python 3.12（命令行可用 py -3.12）。" -ForegroundColor Red
        exit 1
    }
}
Write-Host "venv 复核：$VenvPython"
& $VenvPython -c "import sys; print('复核 python：' + sys.executable)"

# ---- 2. 依赖（锁版本，见 requirements.txt）----
Write-Host "按 requirements.txt 安装依赖（锁版本）…"
& $VenvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "依赖安装失败（exit $LASTEXITCODE）：请检查网络或 requirements.txt 锁版本是否仍可获取。" -ForegroundColor Red
    exit 1
}

# ---- 3. 端口占用：只提示，不杀任何进程 ----
$busy = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    $owner = ($busy | Select-Object -First 1).OwningProcess
    Write-Host "端口 $Port 已被占用（进程 PID $owner）。本程序不会结束该进程，也不会改绑 0.0.0.0。" -ForegroundColor Red
    Write-Host "请换端口后重试，例如：`$env:V2O_PORT=8900; .\start.ps1"
    exit 2
}

# ---- 4. 进程级 UTF-8（不改系统 code page）----
$env:PYTHONUTF8 = "1"
$env:V2O_PORT   = $Port

Write-Host "用 $VenvPython 启动 懒得笔记 本机控制台…"
Write-Host "已起 $Url （Ctrl+C 停止）"
try {
    & $VenvPython (Join-Path $Root "app/server.py")
}
finally {
    Write-Host "已停止：$Url"
}
exit $LASTEXITCODE

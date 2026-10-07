# Windows PyYAML 编译错误快速修复脚本
# 
# 问题: PyYAML 在 Windows 上安装时出现 "AttributeError: cython_sources" 错误
# 原因: PyYAML 需要编译，但缺少 C 编译器或 Cython 依赖
# 
# 使用方法:
#   .\scripts\fix_pyyaml_windows.ps1

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 79) -ForegroundColor Cyan
Write-Host "🔧 Windows PyYAML 编译错误修复脚本" -ForegroundColor Cyan
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 79) -ForegroundColor Cyan

# 检查 Python 环境
Write-Host "`n📋 检查 Python 环境..." -ForegroundColor Yellow
$pythonCmd = if (Test-Path ".\.venv\Scripts\python.exe") {
    ".\.venv\Scripts\python"
} else {
    "python"
}

try {
    $pythonVersion = & $pythonCmd --version 2>&1
    Write-Host "✅ Python 版本: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ 未找到 Python，请先安装 Python 3.10+" -ForegroundColor Red
    exit 1
}

# 升级 pip、setuptools、wheel
Write-Host "`n⬆️  升级 pip、setuptools、wheel..." -ForegroundColor Yellow
$upgradeCmd = "$pythonCmd -m pip install --upgrade pip setuptools wheel -i https://pypi.tuna.tsinghua.edu.cn/simple"
Write-Host "执行: $upgradeCmd" -ForegroundColor Gray
Invoke-Expression $upgradeCmd

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 升级失败" -ForegroundColor Red
    exit 1
}

# 安装项目依赖（使用 --only-binary 避免编译 PyYAML）
Write-Host "`n📦 安装项目依赖（使用预编译包）..." -ForegroundColor Yellow
$installCmd = "$pythonCmd -m pip install -e . --only-binary pyyaml -i https://pypi.tuna.tsinghua.edu.cn/simple"
Write-Host "执行: $installCmd" -ForegroundColor Gray
Write-Host "💡 使用 --only-binary pyyaml 避免编译错误" -ForegroundColor Cyan

$startTime = Get-Date
Invoke-Expression $installCmd

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n❌ 项目依赖安装失败" -ForegroundColor Red
    Write-Host "`n💡 请查看错误信息，或在 GitHub Issues 中反馈" -ForegroundColor Yellow
    exit 1
}

$endTime = Get-Date
$duration = $endTime - $startTime

Write-Host "`n" -NoNewline
Write-Host ("=" * 80) -ForegroundColor Cyan
Write-Host "✅ 安装完成！" -ForegroundColor Green
Write-Host "⏱️  耗时: $($duration.TotalSeconds) 秒" -ForegroundColor Green
Write-Host ("=" * 80) -ForegroundColor Cyan

# 验证安装
Write-Host "`n🔍 验证安装..." -ForegroundColor Yellow
$verifyCmd = "$pythonCmd -c `"import yaml; import finagentlab; print('✅ 验证成功')`""
try {
    Invoke-Expression $verifyCmd
} catch {
    Write-Host "⚠️  验证失败，但安装可能已完成" -ForegroundColor Yellow
}

# 显示后续步骤
Write-Host "`n📝 后续步骤:" -ForegroundColor Yellow
Write-Host "  1. 复制 .env.example 为 .env 并配置 API Key" -ForegroundColor White
Write-Host "  2. 运行 Web 界面: streamlit run web/main.py" -ForegroundColor White
Write-Host "  3. 或使用 CLI: python -m cli.main" -ForegroundColor White

Write-Host "`n🎉 祝使用愉快！" -ForegroundColor Green


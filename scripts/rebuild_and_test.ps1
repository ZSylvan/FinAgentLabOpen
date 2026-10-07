# Docker重建和测试脚本 (PowerShell版本)
# 修复KeyError后的完整测试流程

Write-Host "🚀 Docker重建和日志测试" -ForegroundColor Green
Write-Host "========================" -ForegroundColor Green

# 1. 停止现有容器
Write-Host ""
Write-Host "🛑 停止现有容器..." -ForegroundColor Yellow
docker-compose down

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 容器已停止" -ForegroundColor Green
} else {
    Write-Host "⚠️ 停止容器时出现警告" -ForegroundColor Yellow
}

# 2. 重新构建镜像
Write-Host ""
Write-Host "🔨 重新构建Docker镜像..." -ForegroundColor Yellow
Write-Host "💡 这可能需要几分钟时间..." -ForegroundColor Gray

docker-compose build

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 镜像构建成功" -ForegroundColor Green
} else {
    Write-Host "❌ 镜像构建失败" -ForegroundColor Red
    exit 1
}

# 3. 启动容器
Write-Host ""
Write-Host "🚀 启动容器..." -ForegroundColor Yellow
docker-compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 容器启动成功" -ForegroundColor Green
} else {
    Write-Host "❌ 容器启动失败" -ForegroundColor Red
    exit 1
}

# 4. 等待容器完全启动
Write-Host ""
Write-Host "⏳ 等待容器完全启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# 5. 检查容器状态
Write-Host ""
Write-Host "📊 检查容器状态..." -ForegroundColor Yellow
docker-compose ps

# 6. 运行简单日志测试
Write-Host ""
Write-Host "🧪 运行简单日志测试..." -ForegroundColor Yellow
$testResult = docker exec FinAgentLab-web python simple_log_test.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 简单日志测试通过" -ForegroundColor Green
    Write-Host $testResult
} else {
    Write-Host "❌ 简单日志测试失败" -ForegroundColor Red
    Write-Host $testResult
}

# 7. 检查本地日志文件
Write-Host ""
Write-Host "📁 检查本地日志文件..." -ForegroundColor Yellow
if (Test-Path "logs") {
    $logFiles = Get-ChildItem "logs\*.log*" -ErrorAction SilentlyContinue
    if ($logFiles) {
        Write-Host "✅ 找到日志文件:" -ForegroundColor Green
        foreach ($file in $logFiles) {
            $size = [math]::Round($file.Length / 1KB, 2)
            Write-Host "   📄 $($file.Name) ($size KB)" -ForegroundColor Gray
        }
    } else {
        Write-Host "⚠️ 本地logs目录中未找到日志文件" -ForegroundColor Yellow
    }
} else {
    Write-Host "❌ logs目录不存在" -ForegroundColor Red
}

# 8. 检查容器内日志文件
Write-Host ""
Write-Host "🐳 检查容器内日志文件..." -ForegroundColor Yellow
$containerLogs = docker exec FinAgentLab-web ls -la /app/logs/
Write-Host $containerLogs

# 9. 查看最近的Docker日志
Write-Host ""
Write-Host "📋 查看最近的Docker日志..." -ForegroundColor Yellow
Write-Host "================================" -ForegroundColor Gray
docker logs --tail 20 FinAgentLab-web
Write-Host "================================" -ForegroundColor Gray

# 10. 尝试触发应用日志
Write-Host ""
Write-Host "🎯 尝试触发应用日志..." -ForegroundColor Yellow
$appTest = docker exec FinAgentLab-web python -c "
import sys
sys.path.insert(0, '/app')
try:
    from finagentlab.utils.logging_init import setup_web_logging
    logger = setup_web_logging()
    logger.info('🧪 应用日志测试成功')
    print('✅ 应用日志测试完成')
except Exception as e:
    print(f'❌ 应用日志测试失败: {e}')
"

Write-Host $appTest

# 11. 最终检查
Write-Host ""
Write-Host "🔍 最终检查..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

if (Test-Path "logs") {
    $finalLogFiles = Get-ChildItem "logs\*.log*" -ErrorAction SilentlyContinue
    if ($finalLogFiles) {
        Write-Host "✅ 最终检查 - 找到日志文件:" -ForegroundColor Green
        foreach ($file in $finalLogFiles) {
            $size = [math]::Round($file.Length / 1KB, 2)
            $lastWrite = $file.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
            Write-Host "   📄 $($file.Name) ($size KB) - 最后修改: $lastWrite" -ForegroundColor Gray
            
            # 显示最后几行
            if ($file.Length -gt 0) {
                Write-Host "   📋 最后3行内容:" -ForegroundColor Cyan
                $content = Get-Content $file.FullName -Tail 3 -ErrorAction SilentlyContinue
                foreach ($line in $content) {
                    Write-Host "      $line" -ForegroundColor White
                }
            }
        }
    }
}

Write-Host ""
Write-Host "🎉 测试完成！" -ForegroundColor Green
Write-Host ""
Write-Host "💡 常用命令:" -ForegroundColor Yellow
Write-Host "   实时查看日志: Get-Content logs\finagentlab.log -Wait" -ForegroundColor Gray
Write-Host "   查看Docker日志: docker-compose logs -f web" -ForegroundColor Gray
Write-Host "   重启服务: docker-compose restart web" -ForegroundColor Gray
Write-Host "   进入容器: docker exec -it FinAgentLab-web bash" -ForegroundColor Gray
Write-Host ""
Write-Host "🌐 Web界面: http://localhost:8501" -ForegroundColor Cyan

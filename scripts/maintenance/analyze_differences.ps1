# PowerShell脚本：分析FinAgentLab和FinAgentLab的差异
# 用于确定可贡献的改进功能

Write-Host "🔍 分析项目差异" -ForegroundColor Blue
Write-Host "==================" -ForegroundColor Blue

# 设置路径
$OriginalPath = "C:\code\FinAgentLab"
$EnhancedPath = "C:\code\FinAgentLab"

# 检查目录是否存在
if (-not (Test-Path $OriginalPath)) {
    Write-Host "❌ 错误：未找到FinAgentLab目录" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $EnhancedPath)) {
    Write-Host "❌ 错误：未找到FinAgentLab目录" -ForegroundColor Red
    exit 1
}

Write-Host "✅ 目录检查通过" -ForegroundColor Green

# 1. 对比目录结构
Write-Host "`n📁 目录结构对比：" -ForegroundColor Yellow

Write-Host "`n原项目 (FinAgentLab)：" -ForegroundColor Cyan
Get-ChildItem $OriginalPath -Directory | Select-Object Name | Format-Table -HideTableHeaders

Write-Host "增强版 (FinAgentLab)：" -ForegroundColor Cyan
Get-ChildItem $EnhancedPath -Directory | Select-Object Name | Format-Table -HideTableHeaders

# 2. 对比finagentlab核心目录
Write-Host "📊 核心模块对比 (finagentlab/)：" -ForegroundColor Yellow

$OriginalCore = Join-Path $OriginalPath "finagentlab"
$EnhancedCore = Join-Path $EnhancedPath "finagentlab"

if ((Test-Path $OriginalCore) -and (Test-Path $EnhancedCore)) {
    Write-Host "`n原项目核心模块：" -ForegroundColor Cyan
    Get-ChildItem $OriginalCore -Directory | Select-Object Name | Format-Table -HideTableHeaders
    
    Write-Host "增强版核心模块：" -ForegroundColor Cyan
    Get-ChildItem $EnhancedCore -Directory | Select-Object Name | Format-Table -HideTableHeaders
    
    # 找出增强版独有的目录
    $OriginalDirs = (Get-ChildItem $OriginalCore -Directory).Name
    $EnhancedDirs = (Get-ChildItem $EnhancedCore -Directory).Name
    $NewDirs = $EnhancedDirs | Where-Object { $_ -notin $OriginalDirs }
    
    if ($NewDirs) {
        Write-Host "🆕 增强版新增目录：" -ForegroundColor Green
        $NewDirs | ForEach-Object { Write-Host "  + $_" -ForegroundColor Green }
    }
}

# 3. 对比dataflows目录（重点关注）
Write-Host "`n🔧 数据流模块对比 (dataflows/)：" -ForegroundColor Yellow

$OriginalDataflows = Join-Path $OriginalCore "dataflows"
$EnhancedDataflows = Join-Path $EnhancedCore "dataflows"

if ((Test-Path $OriginalDataflows) -and (Test-Path $EnhancedDataflows)) {
    Write-Host "`n原项目dataflows文件：" -ForegroundColor Cyan
    Get-ChildItem $OriginalDataflows -File -Filter "*.py" | Select-Object Name | Format-Table -HideTableHeaders
    
    Write-Host "增强版dataflows文件：" -ForegroundColor Cyan
    Get-ChildItem $EnhancedDataflows -File -Filter "*.py" | Select-Object Name | Format-Table -HideTableHeaders
    
    # 找出新增的文件
    $OriginalFiles = (Get-ChildItem $OriginalDataflows -File -Filter "*.py").Name
    $EnhancedFiles = (Get-ChildItem $EnhancedDataflows -File -Filter "*.py").Name
    $NewFiles = $EnhancedFiles | Where-Object { $_ -notin $OriginalFiles }
    
    if ($NewFiles) {
        Write-Host "🆕 增强版新增文件：" -ForegroundColor Green
        $NewFiles | ForEach-Object { Write-Host "  + $_" -ForegroundColor Green }
    }
    
    # 检查修改的文件（通过文件大小简单判断）
    Write-Host "`n📝 可能修改的文件：" -ForegroundColor Yellow
    foreach ($file in $OriginalFiles) {
        $originalFile = Join-Path $OriginalDataflows $file
        $enhancedFile = Join-Path $EnhancedDataflows $file
        
        if (Test-Path $enhancedFile) {
            $originalSize = (Get-Item $originalFile).Length
            $enhancedSize = (Get-Item $enhancedFile).Length
            
            if ($originalSize -ne $enhancedSize) {
                $sizeDiff = $enhancedSize - $originalSize
                Write-Host "  📄 $file (大小变化: $sizeDiff 字节)" -ForegroundColor Cyan
            }
        }
    }
}

# 4. 检查重要的新增功能
Write-Host "`n🚀 重要改进功能识别：" -ForegroundColor Yellow

# 检查缓存管理器
$CacheManager = Join-Path $EnhancedDataflows "cache_manager.py"
if (Test-Path $CacheManager) {
    Write-Host "✅ 发现缓存管理器：cache_manager.py" -ForegroundColor Green
}

$OptimizedUSData = Join-Path $EnhancedDataflows "optimized_us_data.py"
if (Test-Path $OptimizedUSData) {
    Write-Host "✅ 发现优化美股数据：optimized_us_data.py" -ForegroundColor Green
}

$DBCacheManager = Join-Path $EnhancedDataflows "db_cache_manager.py"
if (Test-Path $DBCacheManager) {
    Write-Host "✅ 发现数据库缓存管理：db_cache_manager.py" -ForegroundColor Green
}

# 5. 检查配置管理
$ConfigDir = Join-Path $EnhancedCore "config"
if (Test-Path $ConfigDir) {
    Write-Host "✅ 发现配置管理目录：config/" -ForegroundColor Green
    Get-ChildItem $ConfigDir -File -Filter "*.py" | ForEach-Object {
        Write-Host "  📄 $($_.Name)" -ForegroundColor Cyan
    }
}

# 6. 检查Web界面
$WebDir = Join-Path $EnhancedPath "web"
if (Test-Path $WebDir) {
    Write-Host "✅ 发现Web界面：web/" -ForegroundColor Green
    Write-Host "  ⚠️ 注意：Web界面可能不适合直接贡献" -ForegroundColor Yellow
}

Write-Host "`n📋 贡献建议：" -ForegroundColor Blue
Write-Host "🥇 第一优先级（高价值，低风险）：" -ForegroundColor Green
Write-Host "  • 智能缓存系统 (cache_manager.py)" -ForegroundColor White
Write-Host "  • 美股数据优化 (optimized_us_data.py)" -ForegroundColor White
Write-Host "  • 数据库缓存管理 (db_cache_manager.py)" -ForegroundColor White

Write-Host "`n🥈 第二优先级（中等价值）：" -ForegroundColor Yellow
Write-Host "  • 配置管理系统 (config/)" -ForegroundColor White
Write-Host "  • 错误处理改进" -ForegroundColor White

Write-Host "`n🥉 第三优先级（需要评估）：" -ForegroundColor Cyan
Write-Host "  • 测试框架改进" -ForegroundColor White
Write-Host "  • 文档增强" -ForegroundColor White

Write-Host "`n❌ 不建议贡献：" -ForegroundColor Red
Write-Host "  • 中文化功能" -ForegroundColor White
Write-Host "  • A股特定功能" -ForegroundColor White
Write-Host "  • Web界面（除非作为可选功能）" -ForegroundColor White

Write-Host "`n🎯 建议下一步：" -ForegroundColor Blue
Write-Host "1. 检查 cache_manager.py 的具体实现" -ForegroundColor White
Write-Host "2. 分析 optimized_us_data.py 的改进" -ForegroundColor White
Write-Host "3. 准备第一个贡献：智能缓存系统" -ForegroundColor White

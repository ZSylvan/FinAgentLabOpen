# FinAgentLab 目录初始化脚本 (PowerShell版本)
# 创建Docker容器需要的本地目录结构

Write-Host "🚀 FinAgentLab 目录初始化" -ForegroundColor Green
Write-Host "==========================" -ForegroundColor Green

# 获取项目根目录
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "📁 项目根目录: $ProjectRoot" -ForegroundColor Cyan

# 创建必要的目录
$Directories = @(
    "logs",
    "data",
    "data\cache",
    "data\exports", 
    "data\temp",
    "config",
    "config\runtime"
)

Write-Host ""
Write-Host "📂 创建目录结构..." -ForegroundColor Yellow

foreach ($dir in $Directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "✅ 创建目录: $dir" -ForegroundColor Green
    } else {
        Write-Host "📁 目录已存在: $dir" -ForegroundColor Gray
    }
}

# 创建 .gitkeep 文件保持目录结构
Write-Host ""
Write-Host "📝 创建 .gitkeep 文件..." -ForegroundColor Yellow

$GitkeepDirs = @(
    "logs",
    "data\cache",
    "data\exports",
    "data\temp",
    "config\runtime"
)

foreach ($dir in $GitkeepDirs) {
    $gitkeepFile = Join-Path $dir ".gitkeep"
    if (-not (Test-Path $gitkeepFile)) {
        New-Item -ItemType File -Path $gitkeepFile -Force | Out-Null
        Write-Host "✅ 创建: $gitkeepFile" -ForegroundColor Green
    }
}

# 创建日志配置文件
Write-Host ""
Write-Host "📋 创建日志配置文件..." -ForegroundColor Yellow

$LogConfigFile = "config\logging.toml"
if (-not (Test-Path $LogConfigFile)) {
    $LogConfigContent = @'
# FinAgentLab 日志配置文件
[logging]
version = 1
disable_existing_loggers = false

[logging.formatters.standard]
format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
datefmt = "%Y-%m-%d %H:%M:%S"

[logging.formatters.detailed]
format = "%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s"
datefmt = "%Y-%m-%d %H:%M:%S"

[logging.handlers.console]
class = "logging.StreamHandler"
level = "INFO"
formatter = "standard"
stream = "ext://sys.stdout"

[logging.handlers.file]
class = "logging.handlers.RotatingFileHandler"
level = "DEBUG"
formatter = "detailed"
filename = "/app/logs/finagentlab.log"
maxBytes = 104857600  # 100MB
backupCount = 5
encoding = "utf8"

[logging.handlers.error_file]
class = "logging.handlers.RotatingFileHandler"
level = "ERROR"
formatter = "detailed"
filename = "/app/logs/finagentlab_error.log"
maxBytes = 52428800  # 50MB
backupCount = 3
encoding = "utf8"

[logging.loggers.finagentlab]
level = "DEBUG"
handlers = ["console", "file", "error_file"]
propagate = false

[logging.loggers.streamlit]
level = "INFO"
handlers = ["console", "file"]
propagate = false

[logging.loggers.akshare]
level = "WARNING"
handlers = ["file"]
propagate = false

[logging.loggers.tushare]
level = "WARNING"
handlers = ["file"]
propagate = false

[logging.root]
level = "INFO"
handlers = ["console", "file"]
'@
    
    Set-Content -Path $LogConfigFile -Value $LogConfigContent -Encoding UTF8
    Write-Host "✅ 创建日志配置: $LogConfigFile" -ForegroundColor Green
} else {
    Write-Host "📁 日志配置已存在: $LogConfigFile" -ForegroundColor Gray
}

# 更新 .gitignore 文件
Write-Host ""
Write-Host "📝 更新 .gitignore 文件..." -ForegroundColor Yellow

$GitignoreEntries = @(
    "# 日志文件",
    "logs/*.log",
    "logs/*.log.*",
    "",
    "# 数据缓存", 
    "data/cache/*",
    "data/temp/*",
    "!data/cache/.gitkeep",
    "!data/temp/.gitkeep",
    "",
    "# 运行时配置",
    "config/runtime/*",
    "!config/runtime/.gitkeep",
    "",
    "# 导出文件",
    "data/exports/*.pdf",
    "data/exports/*.docx", 
    "data/exports/*.xlsx",
    "!data/exports/.gitkeep"
)

# 检查 .gitignore 是否存在
if (-not (Test-Path ".gitignore")) {
    New-Item -ItemType File -Path ".gitignore" -Force | Out-Null
}

# 读取现有的 .gitignore 内容
$existingContent = Get-Content ".gitignore" -ErrorAction SilentlyContinue

# 添加条目到 .gitignore（如果不存在）
$newEntries = @()
foreach ($entry in $GitignoreEntries) {
    if ($entry -ne "" -and $existingContent -notcontains $entry) {
        $newEntries += $entry
    }
}

if ($newEntries.Count -gt 0) {
    Add-Content -Path ".gitignore" -Value $newEntries
}

Write-Host "✅ 更新 .gitignore 文件" -ForegroundColor Green

# 创建 README 文件
Write-Host ""
Write-Host "📚 创建目录说明文件..." -ForegroundColor Yellow

$ReadmeFile = "logs\README.md"
if (-not (Test-Path $ReadmeFile)) {
    $ReadmeContent = @'
# FinAgentLab 日志目录

此目录用于存储 FinAgentLab 应用的日志文件。

## 日志文件说明

- `finagentlab.log` - 主应用日志文件
- `finagentlab_error.log` - 错误日志文件
- `finagentlab.log.1`, `finagentlab.log.2` 等 - 轮转的历史日志文件

## 日志级别

- **DEBUG** - 详细的调试信息
- **INFO** - 一般信息
- **WARNING** - 警告信息
- **ERROR** - 错误信息
- **CRITICAL** - 严重错误

## 日志轮转

- 主日志文件最大 100MB，保留 5 个历史文件
- 错误日志文件最大 50MB，保留 3 个历史文件

## 获取日志

如果遇到问题需要发送日志给开发者，请发送：
1. `finagentlab.log` - 主日志文件
2. `finagentlab_error.log` - 错误日志文件（如果存在）

## Docker 环境

在 Docker 环境中，此目录映射到容器内的 `/app/logs` 目录。
'@
    
    Set-Content -Path $ReadmeFile -Value $ReadmeContent -Encoding UTF8
    Write-Host "✅ 创建日志说明: $ReadmeFile" -ForegroundColor Green
}

# 显示目录结构
Write-Host ""
Write-Host "📋 目录结构预览:" -ForegroundColor Cyan
Write-Host "=================="

function Show-DirectoryTree {
    param([string]$Path = ".", [int]$Level = 0, [int]$MaxLevel = 3)
    
    if ($Level -gt $MaxLevel) { return }
    
    $items = Get-ChildItem $Path | Where-Object { 
        $_.Name -notlike ".git*" -and 
        $_.Name -notlike "__pycache__*" -and
        $_.Name -notlike "*.pyc"
    } | Sort-Object @{Expression={$_.PSIsContainer}; Descending=$true}, Name
    
    foreach ($item in $items) {
        $indent = "  " * $Level
        $prefix = if ($item.PSIsContainer) { "📁" } else { "📄" }
        Write-Host "$indent$prefix $($item.Name)" -ForegroundColor Gray
        
        if ($item.PSIsContainer -and $Level -lt $MaxLevel) {
            Show-DirectoryTree -Path $item.FullName -Level ($Level + 1) -MaxLevel $MaxLevel
        }
    }
}

Show-DirectoryTree

Write-Host ""
Write-Host "🎉 目录初始化完成！" -ForegroundColor Green
Write-Host ""
Write-Host "💡 接下来的步骤:" -ForegroundColor Yellow
Write-Host "1. 运行 Docker Compose: docker-compose up -d" -ForegroundColor Gray
Write-Host "2. 检查日志文件: Get-ChildItem logs\" -ForegroundColor Gray
Write-Host "3. 实时查看日志: Get-Content logs\finagentlab.log -Wait" -ForegroundColor Gray
Write-Host ""
Write-Host "📁 重要目录说明:" -ForegroundColor Cyan
Write-Host "   logs\     - 应用日志文件" -ForegroundColor Gray
Write-Host "   data\     - 数据缓存和导出文件" -ForegroundColor Gray
Write-Host "   config\   - 运行时配置文件" -ForegroundColor Gray
Write-Host ""
Write-Host "🔧 查看日志的PowerShell命令:" -ForegroundColor Yellow
Write-Host "   Get-Content logs\finagentlab.log -Tail 50" -ForegroundColor Gray
Write-Host "   Get-Content logs\finagentlab.log -Wait" -ForegroundColor Gray

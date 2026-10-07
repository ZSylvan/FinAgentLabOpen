# PowerShell脚本：从Git跟踪中移除docs/contribution目录

Write-Host "🔧 从Git跟踪中移除docs/contribution目录" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue

# 进入项目目录
$ProjectPath = "C:\code\FinAgentLab"
Set-Location $ProjectPath

Write-Host "📍 当前目录：$(Get-Location)" -ForegroundColor Yellow

# 检查docs/contribution目录是否存在
if (Test-Path "docs\contribution") {
    Write-Host "✅ docs\contribution 目录存在" -ForegroundColor Green
    
    # 显示目录内容
    $files = Get-ChildItem "docs\contribution" -Recurse -File
    Write-Host "📁 目录包含 $($files.Count) 个文件" -ForegroundColor Cyan
} else {
    Write-Host "❌ docs\contribution 目录不存在" -ForegroundColor Red
    exit 1
}

# 检查.gitignore是否已经包含docs/contribution/
$gitignoreContent = Get-Content ".gitignore" -ErrorAction SilentlyContinue
if ($gitignoreContent -contains "docs/contribution/") {
    Write-Host "✅ .gitignore 已包含 docs/contribution/" -ForegroundColor Green
} else {
    Write-Host "⚠️ .gitignore 未包含 docs/contribution/" -ForegroundColor Yellow
    Write-Host "正在添加到 .gitignore..." -ForegroundColor Yellow
    
    Add-Content ".gitignore" "`n# 贡献相关文档 (不纳入版本控制)`ndocs/contribution/"
    Write-Host "✅ 已添加到 .gitignore" -ForegroundColor Green
}

# 检查Git状态
Write-Host "`n🔍 检查Git状态..." -ForegroundColor Yellow

try {
    # 检查docs/contribution是否被Git跟踪
    $gitStatus = git status --porcelain docs/contribution/ 2>$null
    
    if ($gitStatus) {
        Write-Host "⚠️ docs/contribution 目录仍被Git跟踪" -ForegroundColor Yellow
        Write-Host "正在从Git跟踪中移除..." -ForegroundColor Yellow
        
        # 从Git跟踪中移除（但保留本地文件）
        git rm -r --cached docs/contribution/ 2>$null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ 已从Git跟踪中移除 docs/contribution/" -ForegroundColor Green
        } else {
            Write-Host "❌ 移除失败，可能目录未被跟踪" -ForegroundColor Red
        }
    } else {
        Write-Host "✅ docs/contribution 目录未被Git跟踪" -ForegroundColor Green
    }
    
    # 检查当前Git状态
    Write-Host "`n📊 当前Git状态：" -ForegroundColor Yellow
    $currentStatus = git status --porcelain
    
    if ($currentStatus) {
        Write-Host "有未提交的更改：" -ForegroundColor Cyan
        $currentStatus | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
        
        # 检查是否有contribution相关的更改
        $contributionChanges = $currentStatus | Where-Object { $_ -match "contribution" }
        if ($contributionChanges) {
            Write-Host "`n⚠️ 发现contribution相关的更改：" -ForegroundColor Yellow
            $contributionChanges | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        }
    } else {
        Write-Host "✅ 工作目录干净" -ForegroundColor Green
    }
    
} catch {
    Write-Host "❌ Git操作失败：$($_.Exception.Message)" -ForegroundColor Red
}

# 验证.gitignore是否生效
Write-Host "`n🧪 验证.gitignore是否生效..." -ForegroundColor Yellow

try {
    # 创建一个测试文件
    $testFile = "docs\contribution\test_ignore.txt"
    "测试文件" | Out-File -FilePath $testFile -Encoding UTF8
    
    # 检查Git是否忽略了这个文件
    $gitCheckIgnore = git check-ignore $testFile 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ .gitignore 正常工作，文件被忽略" -ForegroundColor Green
    } else {
        Write-Host "❌ .gitignore 可能未生效" -ForegroundColor Red
    }
    
    # 删除测试文件
    Remove-Item $testFile -ErrorAction SilentlyContinue
    
} catch {
    Write-Host "⚠️ 无法验证.gitignore：$($_.Exception.Message)" -ForegroundColor Yellow
}

# 显示最终状态
Write-Host "`n📋 最终状态：" -ForegroundColor Blue

Write-Host "1. .gitignore配置：" -ForegroundColor White
if (Get-Content ".gitignore" | Select-String "docs/contribution/") {
    Write-Host "   ✅ docs/contribution/ 已添加到 .gitignore" -ForegroundColor Green
} else {
    Write-Host "   ❌ docs/contribution/ 未在 .gitignore 中" -ForegroundColor Red
}

Write-Host "2. 本地文件：" -ForegroundColor White
if (Test-Path "docs\contribution") {
    $fileCount = (Get-ChildItem "docs\contribution" -Recurse -File).Count
    Write-Host "   ✅ docs\contribution 目录存在，包含 $fileCount 个文件" -ForegroundColor Green
} else {
    Write-Host "   ❌ docs\contribution 目录不存在" -ForegroundColor Red
}

Write-Host "3. Git跟踪状态：" -ForegroundColor White
try {
    $gitLsFiles = git ls-files docs/contribution/ 2>$null
    if ($gitLsFiles) {
        Write-Host "   ⚠️ 仍有文件被Git跟踪" -ForegroundColor Yellow
        Write-Host "   跟踪的文件数：$($gitLsFiles.Count)" -ForegroundColor Gray
    } else {
        Write-Host "   ✅ 没有文件被Git跟踪" -ForegroundColor Green
    }
} catch {
    Write-Host "   ⚠️ 无法检查Git跟踪状态" -ForegroundColor Yellow
}

Write-Host "`n🎯 操作建议：" -ForegroundColor Blue

$gitStatusOutput = git status --porcelain 2>$null
if ($gitStatusOutput | Where-Object { $_ -match "contribution" }) {
    Write-Host "1. 提交.gitignore更改：" -ForegroundColor White
    Write-Host "   git add .gitignore" -ForegroundColor Gray
    Write-Host "   git commit -m 'chore: exclude docs/contribution from version control'" -ForegroundColor Gray
    
    Write-Host "2. 如果有contribution文件的删除记录，也需要提交：" -ForegroundColor White
    Write-Host "   git commit -m 'chore: remove docs/contribution from git tracking'" -ForegroundColor Gray
} else {
    Write-Host "✅ 无需额外操作，docs/contribution 已成功排除在Git管理之外" -ForegroundColor Green
}

Write-Host "`n🎉 操作完成！" -ForegroundColor Green
Write-Host "docs/contribution 目录现在不会被Git管理，但文件仍保留在本地。" -ForegroundColor Cyan

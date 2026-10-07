# 清理未使用的 Docker 数据卷
# 
# 这个脚本会：
# 1. 显示所有数据卷
# 2. 识别未使用的数据卷
# 3. 删除未使用的数据卷（需要确认）

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "🗑️  清理未使用的 Docker 数据卷" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

# 1. 显示所有数据卷
Write-Host "`n📋 当前所有数据卷:" -ForegroundColor Yellow
docker volume ls

# 2. 检查正在使用的数据卷
Write-Host "`n🔍 检查正在使用的数据卷..." -ForegroundColor Yellow

$runningContainers = docker ps --format "{{.Names}}"
$usedVolumes = @()

foreach ($container in $runningContainers) {
    $volumes = docker inspect $container -f '{{range .Mounts}}{{.Name}} {{end}}' 2>$null
    if ($volumes) {
        $usedVolumes += $volumes.Split(' ') | Where-Object { $_ -ne '' }
    }
}

$usedVolumes = $usedVolumes | Select-Object -Unique

Write-Host "`n✅ 正在使用的数据卷:" -ForegroundColor Green
foreach ($vol in $usedVolumes) {
    Write-Host "  - $vol" -ForegroundColor Green
}

# 3. 列出所有 FinAgentLab 相关的数据卷
Write-Host "`n📊 FinAgentLab 相关的数据卷:" -ForegroundColor Yellow

$allVolumes = docker volume ls --format "{{.Name}}" | Where-Object { 
    $_ -like "*finagentlab*" -or $_ -like "*mongodb*" -or $_ -like "*redis*"
}

$volumesToDelete = @()

foreach ($vol in $allVolumes) {
    $isUsed = $usedVolumes -contains $vol
    
    if ($isUsed) {
        Write-Host "  ✅ $vol (正在使用)" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  $vol (未使用)" -ForegroundColor Yellow
        $volumesToDelete += $vol
    }
}

# 4. 显示推荐保留的数据卷
Write-Host "`n💡 推荐保留的数据卷:" -ForegroundColor Cyan
Write-Host "  - finagentlab_mongodb_data (主数据卷)" -ForegroundColor Cyan
Write-Host "  - finagentlab_redis_data (主数据卷)" -ForegroundColor Cyan

# 5. 显示可以删除的数据卷
if ($volumesToDelete.Count -gt 0) {
    Write-Host "`n🗑️  可以删除的数据卷 ($($volumesToDelete.Count) 个):" -ForegroundColor Yellow
    foreach ($vol in $volumesToDelete) {
        Write-Host "  - $vol" -ForegroundColor Yellow
    }
    
    # 6. 询问是否删除
    Write-Host "`n⚠️  警告: 删除数据卷将永久删除其中的数据！" -ForegroundColor Red
    $confirm = Read-Host "是否删除这些未使用的数据卷？(yes/no)"
    
    if ($confirm -eq "yes") {
        Write-Host "`n🗑️  开始删除未使用的数据卷..." -ForegroundColor Yellow
        
        foreach ($vol in $volumesToDelete) {
            Write-Host "  删除: $vol" -ForegroundColor Yellow
            docker volume rm $vol 2>$null
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "    ✅ 已删除" -ForegroundColor Green
            } else {
                Write-Host "    ❌ 删除失败（可能正在使用）" -ForegroundColor Red
            }
        }
        
        Write-Host "`n✅ 清理完成！" -ForegroundColor Green
    } else {
        Write-Host "`n❌ 已取消删除操作" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n✅ 没有未使用的数据卷需要清理" -ForegroundColor Green
}

# 7. 清理匿名数据卷
Write-Host "`n🔍 检查匿名数据卷..." -ForegroundColor Yellow
$anonymousVolumes = docker volume ls -qf "dangling=true"

if ($anonymousVolumes) {
    $anonymousCount = ($anonymousVolumes | Measure-Object).Count
    Write-Host "  发现 $anonymousCount 个匿名数据卷" -ForegroundColor Yellow
    
    $confirmAnonymous = Read-Host "是否删除所有匿名数据卷？(yes/no)"
    
    if ($confirmAnonymous -eq "yes") {
        Write-Host "`n🗑️  删除匿名数据卷..." -ForegroundColor Yellow
        docker volume prune -f
        Write-Host "  ✅ 匿名数据卷已清理" -ForegroundColor Green
    } else {
        Write-Host "  ❌ 已取消删除匿名数据卷" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ✅ 没有匿名数据卷需要清理" -ForegroundColor Green
}

# 8. 显示清理后的数据卷列表
Write-Host "`n📋 清理后的数据卷列表:" -ForegroundColor Cyan
docker volume ls

Write-Host "`n" + "=" * 80 -ForegroundColor Cyan
Write-Host "✅ 清理操作完成！" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Cyan


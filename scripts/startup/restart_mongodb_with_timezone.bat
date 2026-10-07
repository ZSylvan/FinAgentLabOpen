@echo off
echo 🔄 重启MongoDB容器以应用时区配置...

echo 📋 当前容器状态:
docker ps -a --filter "name=finagentlab-mongodb"

echo.
echo 🛑 停止MongoDB容器...
docker stop finagentlab-mongodb

echo.
echo 🗑️ 删除MongoDB容器（保留数据）...
docker rm finagentlab-mongodb

echo.
echo 🚀 重新启动MongoDB服务...
docker-compose up -d mongodb

echo.
echo ⏳ 等待MongoDB启动...
timeout /t 10 /nobreak

echo.
echo 📋 检查容器状态:
docker ps --filter "name=finagentlab-mongodb"

echo.
echo 🕐 检查MongoDB时区:
docker exec finagentlab-mongodb date

echo.
echo ✅ MongoDB时区配置完成！
echo 💡 提示：如果需要重启所有服务，请运行：docker-compose restart

pause

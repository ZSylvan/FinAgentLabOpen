#!/bin/bash
# FinAgentLab Docker 启动脚本
# 自动创建必要目录并启动Docker容器

echo "🚀 FinAgentLab Docker 启动"
echo "=========================="

# 检查Docker是否运行
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker未运行，请先启动Docker"
    exit 1
fi

# 检查docker-compose是否可用
if ! command -v docker-compose >/dev/null 2>&1; then
    echo "❌ docker-compose未安装"
    exit 1
fi

# 创建logs目录
echo "📁 创建logs目录..."
mkdir -p logs
chmod 755 logs 2>/dev/null || true
echo "✅ logs目录准备完成"

# 检查.env文件
if [ ! -f ".env" ]; then
    echo "⚠️ .env文件不存在"
    if [ -f ".env.example" ]; then
        echo "📋 复制.env.example到.env"
        cp .env.example .env
        echo "✅ 请编辑.env文件配置API密钥"
    else
        echo "❌ .env.example文件也不存在"
        exit 1
    fi
fi

# 显示当前配置
echo ""
echo "📋 当前配置:"
echo "   项目目录: $(pwd)"
echo "   日志目录: $(pwd)/logs"
echo "   配置文件: .env"

# 启动Docker容器
echo ""
echo "🐳 启动Docker容器..."
docker-compose up -d

# 检查启动状态
echo ""
echo "📊 检查容器状态..."
docker-compose ps

# 等待服务启动
echo ""
echo "⏳ 等待服务启动..."
sleep 10

# 检查Web服务
echo ""
echo "🌐 检查Web服务..."
if curl -s http://localhost:8501/_stcore/health >/dev/null 2>&1; then
    echo "✅ Web服务正常运行"
    echo "🌐 访问地址: http://localhost:8501"
else
    echo "⚠️ Web服务可能还在启动中..."
    echo "💡 请稍等片刻后访问: http://localhost:8501"
fi

# 显示日志信息
echo ""
echo "📋 日志信息:"
echo "   日志目录: ./logs/"
echo "   实时查看: tail -f logs/finagentlab.log"
echo "   Docker日志: docker-compose logs -f web"

echo ""
echo "🎉 启动完成！"
echo ""
echo "💡 常用命令:"
echo "   查看状态: docker-compose ps"
echo "   查看日志: docker-compose logs -f web"
echo "   停止服务: docker-compose down"
echo "   重启服务: docker-compose restart web"

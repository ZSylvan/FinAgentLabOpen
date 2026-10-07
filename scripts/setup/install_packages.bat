@echo off
REM 安装必要的Python包 - 使用清华镜像

echo 🔧 安装FinAgentLab必要的Python包
echo =====================================

echo.
echo 🔄 升级pip (重要！避免安装错误)...
python -m pip install --upgrade pip

echo.
echo 📦 使用清华大学镜像安装包...
echo 镜像地址: https://pypi.tuna.tsinghua.edu.cn/simple/

echo.
echo 📥 安装pymongo...
python -m pip install pymongo -i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn

echo.
echo 📥 安装redis...
python -m pip install redis -i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn

echo.
echo 📥 安装其他常用包...
python -m pip install pandas requests -i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn

echo.
echo 📊 检查已安装的包...
python -m pip list | findstr -i "pymongo redis pandas"

echo.
echo ✅ 包安装完成!
echo.
echo 💡 提示:
echo 1. 如果安装失败，可以尝试其他镜像:
echo    - 豆瓣: -i https://pypi.douban.com/simple/ --trusted-host pypi.douban.com
echo    - 中科大: -i https://pypi.mirrors.ustc.edu.cn/simple/ --trusted-host pypi.mirrors.ustc.edu.cn
echo.
echo 2. 下一步运行:
echo    python scripts\setup\initialize_system.py
echo.

pause

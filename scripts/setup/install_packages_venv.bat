@echo off
REM 在虚拟环境中安装必要的Python包

echo 🔧 在虚拟环境中安装FinAgentLab必要的Python包
echo ===============================================

echo.
echo 📍 项目目录: %CD%
echo 🐍 激活虚拟环境...

REM 检查虚拟环境是否存在
if not exist "env\Scripts\activate.bat" (
    echo ❌ 虚拟环境不存在: env\Scripts\activate.bat
    echo 💡 请先创建虚拟环境:
    echo    python -m venv env
    echo    env\Scripts\activate.bat
    pause
    exit /b 1
)

REM 激活虚拟环境
call env\Scripts\activate.bat

echo ✅ 虚拟环境已激活
echo 📦 Python路径: 
where python

echo.
echo 📊 当前pip版本:
python -m pip --version

echo.
echo 🔧 升级pip (使用清华镜像)...
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn

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
echo 🧪 测试包导入...
python -c "
try:
    import pymongo
    print('✅ pymongo 导入成功')
except ImportError as e:
    print('❌ pymongo 导入失败:', e)

try:
    import redis
    print('✅ redis 导入成功')
except ImportError as e:
    print('❌ redis 导入失败:', e)

try:
    import pandas
    print('✅ pandas 导入成功')
except ImportError as e:
    print('❌ pandas 导入失败:', e)
"

echo.
echo ✅ 包安装完成!
echo.
echo 💡 提示:
echo 1. 虚拟环境已激活，可以继续运行其他脚本
echo 2. 下一步运行:
echo    python scripts\setup\initialize_system.py
echo 3. 或检查系统状态:
echo    python scripts\validation\check_system_status.py
echo.
echo 🎯 虚拟环境使用说明:
echo - 激活: env\Scripts\activate.bat
echo - 退出: deactivate
echo.

pause

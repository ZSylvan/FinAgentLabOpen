#!/usr/bin/env python3
"""
清理不必要的目录和文件
移除自动生成的文件和临时输出
"""

import os
import shutil
from pathlib import Path

# 导入日志模块
from finagentlab.utils.logging_manager import get_logger
logger = get_logger('default')


def cleanup_directories():
    """清理不必要的目录"""
    logger.info(f"🧹 清理不必要的目录和文件")
    logger.info(f"=")
    
    # 项目根目录
    project_root = Path(".")
    
    # 需要清理的目录
    cleanup_dirs = [
        "finagentlab.egg-info",
        "enhanced_analysis_reports",
        "__pycache__",
        ".pytest_cache",
    ]
    
    # 需要清理的文件模式
    cleanup_patterns = [
        "*.pyc",
        "*.pyo", 
        "*.pyd",
        ".DS_Store",
        "Thumbs.db"
    ]
    
    cleaned_count = 0
    
    # 清理目录
    for dir_name in cleanup_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path)
                logger.info(f"✅ 删除目录: {dir_name}")
                cleaned_count += 1
            except Exception as e:
                logger.error(f"❌ 删除失败 {dir_name}: {e}")
    
    # 递归清理文件
    for pattern in cleanup_patterns:
        for file_path in project_root.rglob(pattern):
            try:
                file_path.unlink()
                logger.info(f"✅ 删除文件: {file_path}")
                cleaned_count += 1
            except Exception as e:
                logger.error(f"❌ 删除失败 {file_path}: {e}")
    
    return cleaned_count

def update_gitignore():
    """更新.gitignore文件"""
    logger.info(f"\n📝 更新.gitignore文件")
    logger.info(f"=")
    
    gitignore_path = Path(".gitignore")
    
    # 需要添加的忽略规则
    ignore_rules = [
        "# Python包元数据",
        "*.egg-info/",
        "finagentlab.egg-info/",
        "",
        "# 临时输出文件", 
        "enhanced_analysis_reports/",
        "analysis_reports/",
        "",
        "# Python缓存",
        "__pycache__/",
        "*.py[cod]",
        "*$py.class",
        ".pytest_cache/",
        "",
        "# 系统文件",
        ".DS_Store",
        "Thumbs.db",
        "",
        "# IDE文件",
        ".vscode/settings.json",
        ".idea/",
        "",
        "# 日志文件",
        "*.log",
        "logs/",
    ]
    
    try:
        # 读取现有内容
        existing_content = ""
        if gitignore_path.exists():
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
        
        # 检查哪些规则需要添加
        new_rules = []
        for rule in ignore_rules:
            if rule.strip() and rule not in existing_content:
                new_rules.append(rule)
        
        if new_rules:
            # 添加新规则
            with open(gitignore_path, 'a', encoding='utf-8') as f:
                f.write("\n# 自动清理脚本添加的规则\n")
                for rule in new_rules:
                    f.write(f"{rule}\n")
            
            logger.info(f"✅ 添加了 {len(new_rules)} 条新的忽略规则")
        else:
            logger.info(f"✅ .gitignore已经是最新的")
            
    except Exception as e:
        logger.error(f"❌ 更新.gitignore失败: {e}")

def main():
    """主函数"""
    logger.info(f"🧹 FinAgentLab 目录清理工具")
    logger.info(f"=")
    logger.info(f"💡 目标: 清理自动生成的文件和不必要的目录")
    logger.info(f"=")
    
    # 清理目录和文件
    cleaned_count = cleanup_directories()
    
    # 更新gitignore
    update_gitignore()
    
    # 总结
    logger.info(f"\n📊 清理总结")
    logger.info(f"=")
    logger.info(f"✅ 清理了 {cleaned_count} 个文件/目录")
    logger.info(f"📝 更新了 .gitignore 文件")
    
    logger.info(f"\n🎉 清理完成！项目目录更加整洁")
    logger.info(f"\n💡 建议:")
    logger.info(f"   1. 检查git状态: git status")
    logger.info(f"   2. 提交清理更改: git add . && git commit -m '清理不必要的目录和文件'")

if __name__ == "__main__":
    main()

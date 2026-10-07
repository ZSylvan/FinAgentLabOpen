#!/usr/bin/env python3
"""
测试AKShare数据源优先级修复
验证AKShare已被设置为第一优先级数据源
"""

import os
import sys

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_default_data_source():
    """测试默认数据源设置"""
    print("🔧 测试默认数据源设置")
    print("=" * 60)
    
    try:
        from finagentlab.dataflows.data_source_manager import DataSourceManager, ChinaDataSource
        
        # 创建数据源管理器
        manager = DataSourceManager()
        
        print(f"📊 默认数据源: {manager.default_source.value}")
        print(f"📊 当前数据源: {manager.current_source.value}")
        print(f"📊 可用数据源: {[s.value for s in manager.available_sources]}")
        
        # 验证默认数据源是AKShare
        if manager.default_source == ChinaDataSource.AKSHARE:
            print("✅ 默认数据源正确设置为AKShare")
            return True
        else:
            print(f"❌ 默认数据源错误: 期望akshare，实际{manager.default_source.value}")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_fallback_priority():
    """测试备用数据源优先级"""
    print("\n🔧 测试备用数据源优先级")
    print("=" * 60)
    
    try:
        from finagentlab.dataflows.data_source_manager import DataSourceManager, ChinaDataSource
        
        manager = DataSourceManager()
        
        # 模拟当前数据源失败，测试备用数据源顺序
        print("📊 模拟数据源失败，检查备用数据源优先级...")
        
        # 检查_try_fallback_sources方法中的fallback_order
        # 这里我们通过检查源代码来验证
        import inspect
        source_code = inspect.getsource(manager._try_fallback_sources)
        
        if "ChinaDataSource.AKSHARE" in source_code:
            # 检查AKShare是否在Tushare之前
            akshare_pos = source_code.find("ChinaDataSource.AKSHARE")
            tushare_pos = source_code.find("ChinaDataSource.TUSHARE")
            
            if akshare_pos < tushare_pos and akshare_pos != -1:
                print("✅ 备用数据源优先级正确: AKShare > Tushare")
                return True
            else:
                print("❌ 备用数据源优先级错误: AKShare应该在Tushare之前")
                return False
        else:
            print("❌ 备用数据源配置中未找到AKShare")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_environment_variable_override():
    """测试环境变量覆盖"""
    print("\n🔧 测试环境变量覆盖")
    print("=" * 60)
    
    try:
        # 保存原始环境变量
        original_env = os.getenv('DEFAULT_CHINA_DATA_SOURCE')
        
        # 测试设置为tushare
        os.environ['DEFAULT_CHINA_DATA_SOURCE'] = 'tushare'
        
        from finagentlab.dataflows.data_source_manager import DataSourceManager, ChinaDataSource
        
        # 重新导入以获取新的环境变量
        import importlib
        import finagentlab.dataflows.data_source_manager as dsm
        importlib.reload(dsm)
        
        manager = dsm.DataSourceManager()
        
        if manager.default_source == ChinaDataSource.TUSHARE:
            print("✅ 环境变量覆盖功能正常")
            result = True
        else:
            print(f"❌ 环境变量覆盖失败: 期望tushare，实际{manager.default_source.value}")
            result = False
        
        # 恢复原始环境变量
        if original_env:
            os.environ['DEFAULT_CHINA_DATA_SOURCE'] = original_env
        else:
            os.environ.pop('DEFAULT_CHINA_DATA_SOURCE', None)
        
        return result
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_akshare_availability():
    """测试AKShare可用性"""
    print("\n🔧 测试AKShare可用性")
    print("=" * 60)
    
    try:
        import akshare as ak
        print(f"✅ AKShare库已安装: v{ak.__version__}")
        
        # 简单测试AKShare功能
        print("📊 测试AKShare基本功能...")
        
        # 这里不实际调用API，只测试导入
        from finagentlab.dataflows.akshare_utils import get_china_stock_data_akshare
        print("✅ AKShare工具函数导入成功")
        
        return True
        
    except ImportError:
        print("❌ AKShare库未安装")
        return False
    except Exception as e:
        print(f"❌ AKShare测试失败: {e}")
        return False

def test_data_source_switching():
    """测试数据源切换功能"""
    print("\n🔧 测试数据源切换功能")
    print("=" * 60)
    
    try:
        from finagentlab.dataflows.data_source_manager import DataSourceManager, ChinaDataSource
        
        manager = DataSourceManager()
        original_source = manager.current_source
        
        print(f"📊 原始数据源: {original_source.value}")
        
        # 测试切换到不同数据源
        test_sources = [ChinaDataSource.TUSHARE, ChinaDataSource.BAOSTOCK]
        
        for source in test_sources:
            if source in manager.available_sources:
                success = manager.set_current_source(source)
                if success:
                    print(f"✅ 成功切换到: {source.value}")
                    current = manager.get_current_source()
                    if current == source:
                        print(f"✅ 当前数据源确认: {current.value}")
                    else:
                        print(f"❌ 数据源切换验证失败")
                        return False
                else:
                    print(f"❌ 切换到{source.value}失败")
                    return False
            else:
                print(f"⚠️ 数据源{source.value}不可用，跳过测试")
        
        # 恢复原始数据源
        manager.set_current_source(original_source)
        print(f"📊 恢复原始数据源: {original_source.value}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("🧪 AKShare数据源优先级修复验证")
    print("=" * 80)
    
    tests = [
        ("默认数据源设置", test_default_data_source),
        ("备用数据源优先级", test_fallback_priority),
        ("环境变量覆盖", test_environment_variable_override),
        ("AKShare可用性", test_akshare_availability),
        ("数据源切换功能", test_data_source_switching),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 执行测试: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ 测试{test_name}异常: {e}")
            results.append((test_name, False))
    
    # 总结结果
    print("\n" + "=" * 80)
    print("📊 测试结果总结:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 总体结果: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！AKShare数据源优先级修复成功！")
        return True
    else:
        print("⚠️ 部分测试失败，需要进一步检查。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
快速测试BaoStock数据源
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_baostock_import():
    """测试BaoStock导入"""
    print("🔍 测试BaoStock导入...")
    try:
        import baostock as bs
        print(f"✅ BaoStock导入成功")
        print(f"   版本: {bs.__version__}")
        return True
    except ImportError as e:
        print(f"❌ BaoStock导入失败: {e}")
        return False

def test_baostock_connection():
    """测试BaoStock连接"""
    print("\n🔍 测试BaoStock连接...")
    try:
        import baostock as bs
        
        # 登录系统
        lg = bs.login()
        if lg.error_code != '0':
            print(f"❌ BaoStock登录失败: {lg.error_msg}")
            return False
        
        print(f"✅ BaoStock登录成功")
        
        # 测试获取数据
        rs = bs.query_history_k_data_plus(
            "sz.000001",  # 平安银行
            "date,code,open,high,low,close,volume",
            start_date='2025-07-01',
            end_date='2025-07-12',
            frequency="d"
        )
        
        if rs.error_code != '0':
            print(f"❌ BaoStock数据获取失败: {rs.error_msg}")
            bs.logout()
            return False
        
        # 获取数据
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        print(f"✅ BaoStock数据获取成功")
        print(f"   数据条数: {len(data_list)}")
        if data_list:
            print(f"   最新数据: {data_list[-1]}")
        
        # 登出系统
        bs.logout()
        return True
        
    except Exception as e:
        print(f"❌ BaoStock连接异常: {e}")
        try:
            import baostock as bs
            bs.logout()
        except:
            pass
        return False

def test_data_source_manager():
    """测试数据源管理器中的BaoStock"""
    print("\n🔍 测试数据源管理器中的BaoStock...")
    try:
        from finagentlab.dataflows.data_source_manager import DataSourceManager
        
        manager = DataSourceManager()
        print(f"✅ 数据源管理器初始化成功")
        print(f"   当前数据源: {manager.current_source.value}")
        print(f"   可用数据源: {[s.value for s in manager.available_sources]}")
        
        # 检查BaoStock是否在可用数据源中
        available_sources = [s.value for s in manager.available_sources]
        if 'baostock' in available_sources:
            print(f"✅ BaoStock已被识别为可用数据源")
            return True
        else:
            print(f"❌ BaoStock未被识别为可用数据源")
            return False
            
    except Exception as e:
        print(f"❌ 数据源管理器测试异常: {e}")
        return False

def main():
    """主测试函数"""
    print("🧪 BaoStock快速测试")
    print("=" * 40)
    
    results = []
    
    # 1. 测试导入
    import_result = test_baostock_import()
    results.append(('BaoStock导入', import_result))
    
    # 2. 测试连接（只有导入成功才测试）
    if import_result:
        connection_result = test_baostock_connection()
        results.append(('BaoStock连接', connection_result))
        
        # 3. 测试数据源管理器
        manager_result = test_data_source_manager()
        results.append(('数据源管理器', manager_result))
    
    # 统计结果
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n📊 测试结果:")
    print("=" * 40)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n📈 总体结果: {passed}/{total}")
    
    if passed == total:
        print(f"🎉 BaoStock配置完成！")
        print(f"✅ 现在中国股票数据源包括:")
        print(f"   1. Tushare (主要)")
        print(f"   2. AKShare (备用)")
        print(f"   3. BaoStock (历史数据备用)")
        print(f"   4. TDX (将被淘汰)")
    else:
        print(f"⚠️ BaoStock配置存在问题")
        print(f"❌ 请检查网络连接和库安装")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    
    if success:
        print(f"\n🎯 下一步:")
        print("1. 重新运行完整数据源测试")
        print("2. python tests/test_data_sources_comprehensive.py")
    else:
        print(f"\n🔧 故障排除:")
        print("1. 检查网络连接")
        print("2. 重新安装: pip install baostock")
        print("3. 查看BaoStock官方文档")

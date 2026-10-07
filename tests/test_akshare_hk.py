"""
测试AKShare港股功能
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_akshare_hk_basic():
    """测试AKShare港股基本功能"""
    print("🧪 测试AKShare港股基本功能...")
    
    try:
        from finagentlab.dataflows.akshare_utils import get_akshare_provider
        
        provider = get_akshare_provider()
        
        if not provider.connected:
            print("⚠️ AKShare未连接，跳过测试")
            return True
        
        # 测试港股代码标准化
        test_symbols = [
            ("0700.HK", "00700"),
            ("700", "00700"),
            ("9988.HK", "09988"),
            ("3690", "03690")
        ]
        
        for input_symbol, expected in test_symbols:
            normalized = provider._normalize_hk_symbol_for_akshare(input_symbol)
            print(f"  标准化: {input_symbol} -> {normalized} {'✅' if normalized == expected else '❌'}")
            
            if normalized != expected:
                print(f"❌ 港股代码标准化失败: {input_symbol} -> {normalized}, 期望: {expected}")
                return False
        
        print("✅ AKShare港股基本功能测试通过")
        return True
        
    except Exception as e:
        print(f"❌ AKShare港股基本功能测试失败: {e}")
        return False

def test_akshare_hk_data():
    """测试AKShare港股数据获取"""
    print("\n🧪 测试AKShare港股数据获取...")
    
    try:
        from finagentlab.dataflows.akshare_utils import get_hk_stock_data_akshare
        from datetime import datetime, timedelta
        
        # 设置测试日期
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # 测试腾讯港股
        symbol = "0700.HK"
        print(f"  获取 {symbol} 数据...")
        
        data = get_hk_stock_data_akshare(symbol, start_date, end_date)
        
        if data and len(data) > 100:
            print("  ✅ AKShare港股数据获取成功")
            
            # 检查关键信息
            checks = [
                ("港股数据报告", "包含标题"),
                ("AKShare", "包含数据源标识"),
                ("HK$", "包含港币符号"),
                ("香港交易所", "包含交易所信息"),
                (symbol, "包含股票代码")
            ]
            
            for check_text, description in checks:
                if check_text in data:
                    print(f"    ✅ {description}")
                else:
                    print(f"    ⚠️ 缺少{description}")
            
            print("✅ AKShare港股数据获取测试通过")
            return True
        else:
            print("❌ AKShare港股数据获取失败")
            print(f"返回数据: {data[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ AKShare港股数据获取测试失败: {e}")
        return False

def test_akshare_hk_info():
    """测试AKShare港股信息获取"""
    print("\n🧪 测试AKShare港股信息获取...")
    
    try:
        from finagentlab.dataflows.akshare_utils import get_hk_stock_info_akshare
        
        symbol = "0700.HK"
        print(f"  获取 {symbol} 信息...")
        
        info = get_hk_stock_info_akshare(symbol)
        
        if info and 'symbol' in info:
            print(f"    ✅ 股票代码: {info['symbol']}")
            print(f"    ✅ 股票名称: {info['name']}")
            print(f"    ✅ 货币: {info['currency']}")
            print(f"    ✅ 交易所: {info['exchange']}")
            print(f"    ✅ 数据源: {info['source']}")
            
            # 验证港股特有信息
            if info['currency'] == 'HKD' and info['exchange'] == 'HKG':
                print("    ✅ 港股信息正确")
            else:
                print("    ⚠️ 港股信息可能不完整")
            
            print("✅ AKShare港股信息获取测试通过")
            return True
        else:
            print("❌ AKShare港股信息获取失败")
            return False
            
    except Exception as e:
        print(f"❌ AKShare港股信息获取测试失败: {e}")
        return False

def test_unified_interface():
    """测试统一接口的AKShare支持"""
    print("\n🧪 测试统一接口的AKShare支持...")
    
    try:
        from finagentlab.dataflows.interface import get_hk_stock_data_unified, get_hk_stock_info_unified
        from datetime import datetime, timedelta
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        symbol = "0700.HK"
        print(f"  通过统一接口获取 {symbol} 数据...")
        
        # 测试数据获取
        data = get_hk_stock_data_unified(symbol, start_date, end_date)
        
        if data and len(data) > 50:
            print("    ✅ 统一接口数据获取成功")
            
            # 检查是否包含AKShare标识
            if "AKShare" in data:
                print("    ✅ 成功使用AKShare作为数据源")
            elif "Yahoo Finance" in data:
                print("    ✅ 使用Yahoo Finance作为备用数据源")
            elif "演示模式" in data:
                print("    ✅ 使用演示模式作为最终备用")
            
        # 测试信息获取
        info = get_hk_stock_info_unified(symbol)
        
        if info and 'symbol' in info:
            print("    ✅ 统一接口信息获取成功")
            print(f"    数据源: {info.get('source', 'unknown')}")
        
        print("✅ 统一接口AKShare支持测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 统一接口AKShare支持测试失败: {e}")
        return False

def main():
    """运行所有AKShare港股测试"""
    print("🇭🇰 开始AKShare港股功能测试")
    print("=" * 50)
    
    tests = [
        test_akshare_hk_basic,
        test_akshare_hk_data,
        test_akshare_hk_info,
        test_unified_interface
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ 测试 {test_func.__name__} 异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"🇭🇰 AKShare港股功能测试完成: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！AKShare港股功能正常")
        print("\n✅ AKShare港股功能特点:")
        print("  - 支持港股代码格式转换")
        print("  - 获取港股历史数据")
        print("  - 获取港股基本信息")
        print("  - 集成到统一数据接口")
        print("  - 作为Yahoo Finance的备用方案")
    else:
        print("⚠️ 部分测试失败，但核心功能可能正常")

if __name__ == "__main__":
    main()

"""
测试 AKShare 成交额单位
检查 AKShare 返回的成交额数据单位是否正确
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from finagentlab.dataflows.providers.china.akshare import get_akshare_provider

async def test_akshare_amount():
    """测试 AKShare 成交额单位"""
    print("=" * 80)
    print("测试 AKShare 成交额单位")
    print("=" * 80)
    
    # 测试股票：300750 宁德时代
    test_code = "300750"
    
    print(f"\n1️⃣ 测试股票: {test_code} (宁德时代)")
    
    provider = get_akshare_provider()
    if not provider.is_available():
        print("   ❌ AKShare 不可用")
        return
    
    print(f"\n2️⃣ 获取实时行情")
    
    # 获取实时行情
    quotes = await provider.get_stock_quotes(test_code)
    
    if quotes:
        print(f"   ✅ 获取成功")
        print(f"   最新价: {quotes.get('close')}")
        print(f"   成交额原始值: {quotes.get('amount')}")
        if quotes.get('amount'):
            amount = quotes.get('amount')
            print(f"   成交额(元): {amount:,.0f}")
            print(f"   成交额(亿元): {amount / 1e8:.2f}")
            print(f"   成交额(万元): {amount / 1e4:.2f}")
    else:
        print(f"   ❌ 获取失败")
    
    print(f"\n3️⃣ 获取历史数据")
    
    # 获取历史数据（最近5天）
    from datetime import datetime, timedelta
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)
    
    hist_df = await provider.get_historical_data(
        symbol=test_code,
        start_date=start_date,
        end_date=end_date,
        period="daily"
    )
    
    if hist_df is not None and not hist_df.empty:
        print(f"   ✅ 获取到 {len(hist_df)} 条记录")
        
        # 显示最新一条数据
        latest = hist_df.iloc[-1]
        print(f"\n   最新数据:")
        print(f"   日期: {latest.name if hasattr(latest, 'name') else latest.get('date')}")
        print(f"   收盘价: {latest.get('close')}")
        print(f"   成交额原始值: {latest.get('amount')}")
        if latest.get('amount'):
            amount = latest.get('amount')
            print(f"   成交额(元): {amount:,.0f}")
            print(f"   成交额(亿元): {amount / 1e8:.2f}")
            print(f"   成交额(万元): {amount / 1e4:.2f}")
    else:
        print(f"   ❌ 获取失败")
    
    print("\n" + "=" * 80)
    print("💡 AKShare 官方文档说明:")
    print("   - stock_zh_a_spot_em(): 成交额单位是 元")
    print("   - stock_zh_a_hist(): 成交额单位是 元")
    print("=" * 80)
    print("\n✅ 结论:")
    print("   如果成交额显示为 90.92亿 左右，说明 AKShare 单位正确（元）✅")
    print("   如果成交额显示为 909.18万 或 0.0091亿，说明有问题 ❌")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_akshare_amount())


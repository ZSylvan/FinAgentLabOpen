#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试AKShare数据源优先级和财务指标修复效果
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from finagentlab.dataflows.optimized_china_data import get_optimized_china_data_provider
from finagentlab.dataflows.akshare_utils import get_akshare_provider
from finagentlab.dataflows.tushare_utils import get_tushare_provider

def test_data_source_connection():
    """测试数据源连接状态"""
    print("=" * 60)
    print("📡 测试数据源连接状态")
    print("=" * 60)
    
    # 测试AKShare连接
    try:
        akshare_provider = get_akshare_provider()
        print(f"🔗 AKShare连接状态: {'✅ 已连接' if akshare_provider.connected else '❌ 未连接'}")
    except Exception as e:
        print(f"❌ AKShare连接失败: {e}")
    
    # 测试Tushare连接
    try:
        tushare_provider = get_tushare_provider()
        print(f"🔗 Tushare连接状态: {'✅ 已连接' if tushare_provider.connected else '❌ 未连接'}")
    except Exception as e:
        print(f"❌ Tushare连接失败: {e}")
    
    print()

def test_akshare_financial_data():
    """测试AKShare财务数据获取"""
    print("=" * 60)
    print("📊 测试AKShare财务数据获取")
    print("=" * 60)
    
    test_symbols = ['000001', '000002', '600519']
    
    try:
        akshare_provider = get_akshare_provider()
        if not akshare_provider.connected:
            print("❌ AKShare未连接，跳过测试")
            return
        
        for symbol in test_symbols:
            print(f"\n🔍 测试股票: {symbol}")
            try:
                financial_data = akshare_provider.get_financial_data(symbol)
                if financial_data:
                    print(f"✅ {symbol}: AKShare财务数据获取成功")
                    
                    # 检查主要财务指标
                    main_indicators = financial_data.get('main_indicators', {})
                    if main_indicators:
                        pe = main_indicators.get('市盈率', main_indicators.get('PE', 'N/A'))
                        pb = main_indicators.get('市净率', main_indicators.get('PB', 'N/A'))
                        roe = main_indicators.get('净资产收益率', main_indicators.get('ROE', 'N/A'))
                        print(f"   📈 PE: {pe}, PB: {pb}, ROE: {roe}")
                    else:
                        print(f"   ⚠️ 主要财务指标为空")
                else:
                    print(f"❌ {symbol}: AKShare财务数据获取失败")
            except Exception as e:
                print(f"❌ {symbol}: AKShare财务数据获取异常: {e}")
    
    except Exception as e:
        print(f"❌ AKShare财务数据测试失败: {e}")
    
    print()

def test_financial_metrics_with_data_source():
    """测试财务指标计算和数据源标识"""
    print("=" * 60)
    print("🧮 测试财务指标计算和数据源标识")
    print("=" * 60)
    
    test_symbols = ['000001', '000002', '600519']
    
    provider = get_optimized_china_data_provider()
    
    for symbol in test_symbols:
        print(f"\n🔍 测试股票: {symbol}")
        try:
            # 获取基本面数据
            fundamentals = provider.get_fundamentals_data(symbol, force_refresh=True)
            
            # 检查数据来源标识
            if "AKShare" in fundamentals:
                data_source = "AKShare"
            elif "Tushare" in fundamentals:
                data_source = "Tushare"
            else:
                data_source = "未知"
            
            print(f"📊 数据来源: {data_source}")
            
            # 提取PE、PB、ROE信息
            lines = fundamentals.split('\n')
            pe_line = next((line for line in lines if '市盈率(PE)' in line), None)
            pb_line = next((line for line in lines if '市净率(PB)' in line), None)
            roe_line = next((line for line in lines if '净资产收益率(ROE)' in line), None)
            
            if pe_line:
                pe_value = pe_line.split('**')[2].strip() if '**' in pe_line else pe_line.split(':')[1].strip()
                print(f"📈 PE: {pe_value}")
            
            if pb_line:
                pb_value = pb_line.split('**')[2].strip() if '**' in pb_line else pb_line.split(':')[1].strip()
                print(f"📈 PB: {pb_value}")
            
            if roe_line:
                roe_value = roe_line.split('**')[2].strip() if '**' in roe_line else roe_line.split(':')[1].strip()
                print(f"📈 ROE: {roe_value}")
            
            # 检查是否有0倍的异常值
            if pe_line and ('0.0倍' in pe_line or '0倍' in pe_line):
                print(f"⚠️ 发现PE异常值: {pe_value}")
            
            if pb_line and ('0.00倍' in pb_line or '0倍' in pb_line):
                print(f"⚠️ 发现PB异常值: {pb_value}")
                
        except Exception as e:
            print(f"❌ {symbol}: 财务指标测试失败: {e}")
    
    print()

def test_data_source_priority():
    """测试数据源优先级"""
    print("=" * 60)
    print("🔄 测试数据源优先级")
    print("=" * 60)
    
    provider = get_optimized_china_data_provider()
    
    # 测试一个股票的财务指标获取过程
    symbol = '000001'
    print(f"🔍 测试股票: {symbol}")
    
    try:
        # 直接调用内部方法测试
        real_metrics = provider._get_real_financial_metrics(symbol, 10.0)
        
        if real_metrics:
            data_source = real_metrics.get('data_source', '未知')
            print(f"✅ 财务数据获取成功")
            print(f"📊 数据来源: {data_source}")
            print(f"📈 PE: {real_metrics.get('pe', 'N/A')}")
            print(f"📈 PB: {real_metrics.get('pb', 'N/A')}")
            print(f"📈 ROE: {real_metrics.get('roe', 'N/A')}")
            
            if data_source == 'AKShare':
                print("✅ 优先使用AKShare数据源成功")
            elif data_source == 'Tushare':
                print("⚠️ 使用Tushare备用数据源")
            else:
                print("❓ 数据源不明确")
        else:
            print("❌ 财务数据获取失败")
            
    except Exception as e:
        print(f"❌ 数据源优先级测试失败: {e}")
    
    print()

def main():
    """主测试函数"""
    print("🚀 开始AKShare数据源优先级和财务指标修复测试")
    print()
    
    # 1. 测试数据源连接
    test_data_source_connection()
    
    # 2. 测试AKShare财务数据获取
    test_akshare_financial_data()
    
    # 3. 测试数据源优先级
    test_data_source_priority()
    
    # 4. 测试财务指标和数据源标识
    test_financial_metrics_with_data_source()
    
    print("=" * 60)
    print("✅ 测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
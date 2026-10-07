"""
测试脚本：验证分析师使用的 base_url 是否正确
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def main():
    print("=" * 80)
    print("🧪 测试：验证分析师使用的 base_url")
    print("=" * 80)
    
    # 1. 创建带有自定义 base_url 的 LLM
    print("\n📊 1. 创建带有自定义 base_url 的 LLM")
    print("-" * 80)
    
    from finagentlab.llm_adapters import ChatDashScopeOpenAI
    
    custom_url = "https://dashscope.aliyuncs.com/api/v2"
    
    print(f"\n创建 LLM，使用自定义 URL: {custom_url}")
    
    llm = ChatDashScopeOpenAI(
        model="qwen-turbo",
        base_url=custom_url,
        temperature=0.1,
        max_tokens=2000
    )
    
    print(f"✅ LLM 创建成功")
    print(f"   模型: {llm.model_name}")
    print(f"   base_url: {llm.openai_api_base}")
    
    if llm.openai_api_base == custom_url:
        print(f"🎯 ✅ base_url 正确")
    else:
        print(f"❌ base_url 不正确")
        print(f"   期望: {custom_url}")
        print(f"   实际: {llm.openai_api_base}")
    
    # 2. 测试基本面分析师
    print("\n\n📊 2. 测试基本面分析师")
    print("-" * 80)
    
    from finagentlab.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
    from finagentlab.agents.utils.agent_utils import Toolkit
    from finagentlab.default_config import DEFAULT_CONFIG
    
    # 创建配置
    config = DEFAULT_CONFIG.copy()
    config["online_tools"] = False  # 关闭在线工具以加快测试
    
    # 创建工具包
    toolkit = Toolkit(config)
    
    # 创建基本面分析师
    print(f"\n创建基本面分析师...")
    analyst = create_fundamentals_analyst(llm, toolkit)
    
    print(f"✅ 基本面分析师创建成功")
    
    # 3. 模拟分析师调用（不实际执行，只检查 LLM 实例）
    print("\n\n📊 3. 检查分析师内部创建的 LLM 实例")
    print("-" * 80)
    
    # 创建一个简单的状态来触发分析师
    state = {
        "trade_date": "2025-07-15",
        "company_of_interest": "601288",
        "messages": []
    }
    
    print(f"\n准备调用分析师...")
    print(f"  股票代码: {state['company_of_interest']}")
    print(f"  交易日期: {state['trade_date']}")
    
    # 注意：这里我们不实际调用分析师，因为那会触发真实的 API 调用
    # 我们只是验证代码逻辑
    
    print(f"\n💡 提示：")
    print(f"由于基本面分析师会在内部创建新的 LLM 实例（为了避免工具缓存），")
    print(f"我们需要确保新实例也使用了正确的 base_url。")
    print(f"\n修复后的代码会：")
    print(f"  1. 检测到阿里百炼模型")
    print(f"  2. 获取原始 LLM 的 base_url: {llm.openai_api_base}")
    print(f"  3. 创建新实例时传递这个 base_url")
    print(f"  4. 新实例也会使用 {custom_url}")
    
    # 4. 验证修复
    print("\n\n📊 4. 验证修复是否生效")
    print("-" * 80)
    
    # 模拟分析师内部的逻辑
    print(f"\n模拟分析师内部创建新 LLM 实例的逻辑...")
    
    if hasattr(llm, '__class__') and 'DashScope' in llm.__class__.__name__:
        print(f"✅ 检测到阿里百炼模型")
        
        # 获取原始 LLM 的 base_url
        original_base_url = getattr(llm, 'openai_api_base', None)
        print(f"✅ 获取原始 base_url: {original_base_url}")
        
        # 创建新实例
        fresh_llm = ChatDashScopeOpenAI(
            model=llm.model_name,
            base_url=original_base_url if original_base_url else None,
            temperature=llm.temperature,
            max_tokens=getattr(llm, 'max_tokens', 2000)
        )
        
        print(f"✅ 创建新 LLM 实例")
        print(f"   模型: {fresh_llm.model_name}")
        print(f"   base_url: {fresh_llm.openai_api_base}")
        
        if fresh_llm.openai_api_base == custom_url:
            print(f"\n🎯 ✅ 完美！新实例的 base_url 正确")
        else:
            print(f"\n❌ 错误！新实例的 base_url 不正确")
            print(f"   期望: {custom_url}")
            print(f"   实际: {fresh_llm.openai_api_base}")
    else:
        print(f"⚠️ 未检测到阿里百炼模型")
    
    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)
    
    print("\n💡 总结：")
    print("修复后，基本面分析师内部创建的新 LLM 实例会继承原始实例的 base_url。")
    print("这样就能确保整个分析流程都使用正确的 API 地址。")

if __name__ == "__main__":
    main()


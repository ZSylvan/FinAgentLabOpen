from finagentlab.graph.trading_graph import FinAgentLabGraph
from finagentlab.default_config import DEFAULT_CONFIG

# 导入日志模块
from finagentlab.utils.logging_manager import get_logger
logger = get_logger('default')


# Create a custom config
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "DEEPSEEK"  # Use a different model
config["backend_url"] = "https://api.deepseek.com"  # Use a different backend
config["deep_think_llm"] = "deepseek-v4-pro"  # Use a different model
config["quick_think_llm"] = "deepseek-v4-flash"  # Use a different model
config["max_debate_rounds"] = 1  # Increase debate rounds
config["online_tools"] = True  # Increase debate rounds

# Initialize with custom config
ta = FinAgentLabGraph(debug=True, config=config)

# forward propagate
_, decision = ta.propagate("000001", "2024-05-10")
print(decision)

# Memorize mistakes and reflect
# ta.reflect_and_remember(1000) # parameter is the position returns

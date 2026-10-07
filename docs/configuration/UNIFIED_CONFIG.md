# 统一配置管理系统

## 📋 概述

统一配置管理系统整合了项目中的多个配置管理模块，提供了一个统一的配置接口，同时保持与现有配置文件格式的兼容性。


> 提示：当前运行时的完整配置清单、默认值与历史别名，请参见 docs/configuration/CONFIG_MATRIX.md。

> 安全与敏感信息：遵循“方案A（分层集中式）”的敏感信息策略：
> - REST 接口不接受/不持久化敏感字段（如 api_key/api_secret/password），提交即清洗忽略；
> - 运行时密钥来自环境变量或厂家目录，接口仅返回 has_value/source 状态；
> - 导出（export）对敏感项脱敏，导入（import）忽略敏感项。


## 🏗️ 架构设计

### 配置层次结构

```
统一配置管理系统
├── 传统配置文件 (config/*.json)
├── FinAgentLab配置 (finagentlab/config/)
├── WebAPI配置 (webapi/models/config.py)
└── 统一配置接口 (webapi/core/unified_config.py)
```

### 核心组件

1. **UnifiedConfigManager**: 统一配置管理器
2. **ConfigPaths**: 配置文件路径管理
3. **配置适配器**: 在不同格式间转换
4. **缓存机制**: 提高配置读取性能

## 🔧 功能特性

### ✅ 向后兼容
- 保持现有 `config/*.json` 文件格式不变
- 支持现有 FinAgentLab 配置系统
- 无需修改现有代码即可使用

### ✅ 统一接口
- 提供标准化的配置数据模型
- 统一的配置读写API
- 自动格式转换和同步

### ✅ 实时同步
- WebAPI修改配置时自动同步到传统格式
- 传统格式修改时自动更新缓存
- 多模块间配置数据一致性

### ✅ 性能优化
- 智能缓存机制
- 文件修改时间检测
- 按需加载配置数据

## 📁 配置文件映射

### 模型配置
- **传统格式**: `config/models.json`
- **统一格式**: `LLMConfig` 对象列表
- **映射关系**:
  ```json
  {
    "provider": "openai",           → ModelProvider.OPENAI
    "model_name": "gpt-3.5-turbo", → model_name
    "api_key": "sk-xxx",           → api_key
    "base_url": "https://...",     → api_base
    "max_tokens": 4000,            → max_tokens
    "temperature": 0.7,            → temperature
    "enabled": true                → enabled
  }
  ```

### 系统设置
- **传统格式**: `config/settings.json`
- **统一格式**: `system_settings` 字典
- **特殊处理**:
  - `default_model` → `default_llm`
  - `tushare_token` → 数据源配置
  - `finnhub_api_key` → 数据源配置


### FinAgentLab 数据来源策略（App 缓存优先开关）
- 键：`ta_use_app_cache`（系统设置）；ENV 覆盖：`TA_USE_APP_CACHE`
- 默认：`false`
- 语义：
  - `true`：优先从 App 缓存数据库读取，未命中回退到直连数据源
  - `false`：保持直连数据源优先，未命中回退到 App 缓存
- 缓存集合（固定名）：
  - 基础信息：`stock_basic_info`
  - 行情快照：`market_quotes`
- 适用范围：FinAgentLab 内部数据获取（基础信息、近实时行情）
- 优先级：DB(system_settings) > ENV > 默认

### 数据源配置
- **来源**: 从 `settings.json` 提取
- **格式**: `DataSourceConfig` 对象列表
- **支持的数据源**:
  - AKShare (默认启用)
  - Tushare (需要token)
  - Finnhub (需要API key)

### 数据库配置
- **来源**: 环境变量
- **格式**: `DatabaseConfig` 对象列表
- **支持的数据库**:
  - MongoDB
  - Redis

## 🚀 使用方法

### 基本用法

```python
from webapi.core.unified_config import unified_config

# 获取LLM配置
llm_configs = unified_config.get_llm_configs()

# 获取系统设置
settings = unified_config.get_system_settings()

# 获取默认模型
default_model = unified_config.get_default_model()

# 设置默认模型
unified_config.set_default_model("gpt-4")

# 保存LLM配置
from webapi.models.config import LLMConfig, ModelProvider
llm_config = LLMConfig(
    provider=ModelProvider.OPENAI,
    model_name="gpt-4",
    api_key="your-api-key",
    api_base="https://api.openai.com/v1"
)
unified_config.save_llm_config(llm_config)
```

### WebAPI集成

```python
from webapi.services.config_service import config_service

# 获取统一系统配置
system_config = await config_service.get_system_config()

# 更新LLM配置（自动同步到传统格式）
await config_service.update_llm_config(llm_config)

# 保存系统配置（同时保存到数据库和传统格式）
await config_service.save_system_config(system_config)
```

### 前端使用

```javascript
// 获取系统配置
const response = await fetch('/api/config/system');
const config = await response.json();

// 添加LLM配置
await fetch('/api/config/llm', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    provider: 'openai',
    model_name: 'gpt-4',
    api_key: 'your-api-key'
  })
});
```

## 🔄 配置迁移

### 自动迁移
系统启动时会自动读取现有配置文件，无需手动迁移。

### 手动迁移工具
```bash
# 运行配置迁移工具
python scripts/migrate_config.py

# 测试配置兼容性
python scripts/test_config_compatibility.py
```

### 迁移步骤
1. **备份现有配置**: 自动备份到 `config_backup/`
2. **读取传统配置**: 解析现有JSON文件
3. **转换格式**: 转换为统一配置格式
4. **验证配置**: 测试配置的正确性
5. **同步保存**: 保存到数据库和传统格式

## 🧪 测试验证

### 兼容性测试
```bash
python scripts/test_config_compatibility.py
```

测试项目包括：
- ✅ 读取传统配置
- ✅ 写入传统配置
- ✅ 统一系统配置
- ✅ 配置同步
- ✅ 默认模型管理
- ✅ 数据源配置
- ✅ 数据库配置
- ✅ 缓存功能

### 性能测试
- 配置读取性能
- 缓存命中率
- 文件同步延迟

## 🔧 配置示例

### 完整配置示例
```json
{
  "config_name": "统一系统配置",
  "llm_configs": [
    {
      "provider": "openai",
      "model_name": "gpt-3.5-turbo",
      "api_key": "sk-xxx",
      "api_base": "https://api.openai.com/v1",
      "max_tokens": 4000,
      "temperature": 0.7,
      "enabled": true
    }
  ],
  "default_llm": "gpt-3.5-turbo",
  "data_source_configs": [
    {
      "name": "AKShare",
      "type": "akshare",
      "endpoint": "https://akshare.akfamily.xyz",
      "enabled": true,
      "priority": 1
    }
  ],
  "system_settings": {
    "max_concurrent_tasks": 3,
    "default_analysis_timeout": 300,
    "enable_cache": true
  }
}
```

## 🚨 注意事项

### 配置文件权限
- 确保配置文件具有适当的读写权限
- 敏感信息（API密钥）应妥善保护

### 配置同步
- WebAPI修改配置会自动同步到传统格式
- 直接修改传统配置文件需要重启服务或清除缓存

### 版本兼容性
- 新版本可能会添加新的配置字段
- 旧版本配置文件会自动升级

## 🔮 未来规划

### 计划功能
- [ ] 配置版本管理
- [ ] 配置变更历史
- [ ] 配置模板系统
- [ ] 配置验证规则
- [ ] 配置热重载

### 性能优化
- [ ] 异步配置加载
- [ ] 分布式配置缓存
- [ ] 配置变更通知

## 🤝 贡献指南

### 添加新配置类型
1. 在 `webapi/models/config.py` 中定义数据模型
2. 在 `UnifiedConfigManager` 中添加相应方法
3. 更新配置同步逻辑
4. 添加测试用例

### 修改配置格式
1. 保持向后兼容性
2. 添加格式转换逻辑
3. 更新文档和示例
4. 运行兼容性测试

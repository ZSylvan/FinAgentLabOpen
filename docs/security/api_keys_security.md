# API密钥安全指南

## 公开版本配置

- 复制 `.env.example` 为 `.env`，将所有 `your_..._here` 替换为本地配置；示例值不能用于真实服务。
- Docker 专用配置可复制 `.env.docker.example` 为 `.env.docker`，再通过 `--env-file .env.docker` 指定。所有真实 `.env` 文件都被 Git 忽略。
- Docker Compose 必须提供 `MONGODB_PASSWORD`、`REDIS_PASSWORD`，使用对应服务时还须提供 `JWT_SECRET`、`CSRF_SECRET` 和 `MONGO_EXPRESS_PASSWORD`。数据库 URL 中的密码须采用 URL 安全字符或编码。
- 原生百度 SDK 使用 `BAIDU_API_KEY` / `BAIDU_SECRET_KEY`；OpenAI 兼容的千帆接入使用 `QIANFAN_API_KEY`；OpenRouter 使用 `OPENROUTER_API_KEY`。
- 手动 Google 测试从 `GOOGLE_API_KEY` 读取凭据；图片分析示例从 `OPENAI_API_KEY` 读取；并发 API 测试从 `FINAGENTLAB_ACCESS_TOKEN` 读取。本地格式校验只使用不可调用服务的 dummy 值。
- 数据迁移脚本的源地址通过 `SOURCE_MONGODB_HOST` 提供，数据库密码从 `MONGODB_PASSWORD` 读取。
- 代码中保留的演示账号、localhost 配置和测试数据仅用于开发。部署真实服务前应更换所有默认账号密码及签名密钥。

任何曾写入 Git 提交的真实 API Key 或访问令牌都应立即吊销并重新生成，即使推送被 GitHub 拒绝。不要使用 Allow secret / Unblock secret 绕过 Push Protection。

## 🚨 重要安全提醒

### ⚠️ 绝对不要做的事情

1. **不要将.env文件提交到Git仓库**
   - .env文件包含敏感的API密钥
   - 一旦提交到公开仓库，密钥可能被恶意使用
   - 即使删除提交，Git历史中仍然存在

2. **不要在代码中硬编码API密钥**
   ```python
   # ❌ 错误做法
   api_key = "dummy-key-aaaaaaaaaaaaaaaaaaaa"
   
   # ✅ 正确做法
   api_key = os.getenv("DASHSCOPE_API_KEY")
   ```

3. **不要在日志中输出完整的API密钥**
   ```python
   # ❌ 错误做法
   print(f"Using API key: {api_key}")
   
   # ✅ 正确做法
   print(f"Using API key: {api_key[:12]}...")
   ```

### ✅ 安全最佳实践

#### 1. 使用环境变量
```bash
# 在.env文件中配置
DASHSCOPE_API_KEY=your_real_api_key_here
FINNHUB_API_KEY=your_real_finnhub_key_here
```

#### 2. 正确的文件权限
```bash
# 设置.env文件只有所有者可读写
chmod 600 .env
```

#### 3. 使用.gitignore
确保.gitignore包含：
```
.env
.env.local
.env.*.local
```

#### 4. 定期轮换API密钥
- 定期更换API密钥
- 如果怀疑密钥泄露，立即更换
- 监控API使用情况，发现异常立即处理

## 🔧 配置步骤

### 1. 复制示例文件
```bash
cp .env.example .env
```

### 2. 编辑.env文件
```bash
# 使用您喜欢的编辑器
notepad .env        # Windows
nano .env           # Linux/Mac
code .env           # VS Code
```

### 3. 填入真实API密钥
```bash
# 阿里百炼API密钥 (推荐)
DASHSCOPE_API_KEY=dummy-key-aaaaaaaaaaaaaaaaaaaa

# 金融数据API密钥 (必需)
FINNHUB_API_KEY=your-real-finnhub-key
```

### 4. 验证配置
```bash
python -m cli.main config
```

## 🔍 API密钥获取指南

### 阿里百炼 (推荐)
1. 访问 https://dashscope.aliyun.com/
2. 注册/登录阿里云账号
3. 开通百炼服务
4. 在控制台获取API密钥

### FinnHub (必需)
1. 访问 https://finnhub.io/
2. 注册免费账号
3. 在Dashboard获取API密钥
4. 免费账户每分钟60次请求

### OpenAI (可选)
1. 访问 https://platform.openai.com/
2. 注册账号并充值
3. 在API Keys页面创建密钥

## 🚨 如果API密钥泄露了怎么办？

### 立即行动
1. **立即撤销泄露的API密钥**
   - 登录对应的API提供商控制台
   - 删除或禁用泄露的密钥

2. **生成新的API密钥**
   - 创建新的API密钥
   - 更新.env文件中的配置

3. **检查使用记录**
   - 查看API使用日志
   - 确认是否有异常使用

4. **更新代码配置**
   - 更新本地.env文件
   - 通知团队成员更新配置

### 预防措施
1. **使用Git hooks**
   - 设置pre-commit hooks检查敏感文件
   - 防止意外提交.env文件

2. **定期审计**
   - 定期检查Git历史
   - 确保没有敏感信息泄露

3. **团队培训**
   - 培训团队成员安全意识
   - 建立安全操作规范

## 📋 安全检查清单

- [ ] .env文件已添加到.gitignore
- [ ] 没有在代码中硬编码API密钥
- [ ] .env文件权限设置正确 (600)
- [ ] 定期轮换API密钥
- [ ] 监控API使用情况
- [ ] 团队成员了解安全规范
- [ ] 设置了pre-commit hooks (可选)

## 🔗 相关资源

- [Git安全最佳实践](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure)
- [环境变量安全指南](https://12factor.net/config)
- [API密钥管理最佳实践](https://owasp.org/www-project-api-security/)

---

**记住：安全无小事，API密钥保护是每个开发者的责任！** 🔐

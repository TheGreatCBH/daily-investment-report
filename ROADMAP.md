# 项目演进路线

记录这个项目从"个人原型脚本"演进到"公开 GitHub 仓库"的所有改造项与执行进度。每完成一项请勾选并写上完成日期。

## 状态约定

- `- [ ]` 待做
- `- [~]` 进行中
- `- [x]` 已完成 ✓ YYYY-MM-DD

---

## 待决策事项

- [x] `watchlist.json` → 拆 `watchlist.example.json`（commit）+ `watchlist.json`（gitignore） ✓ 2026-05-14
- [x] `.claude/settings.local.json` → `.gitignore` 整个 `.claude/` ✓ 2026-05-14
- [x] `reports/` → `.gitignore` 所有生成产物，保留 `reports/.gitkeep` ✓ 2026-05-14
- [x] 模块化包名定为 `daily_report/` ✓ 2026-05-14
- [x] HTML 保持单文件渲染（提取 `render_html.py`），不外置 CSS ✓ 2026-05-14
- [ ] A/H 股新闻方案：A（yfinance 行情 + akshare 新闻）/ B（全 akshare）/ C（DeepSeek 联网搜索）？（项目 5）
- [ ] 邮件 SMTP 通道：Gmail / Outlook / QQ-163 / 第三方 API（SendGrid / Resend）？（项目 4）

---

## 执行清单

### 1. [x] 处理已泄露的 DeepSeek API Key（紧急·必须最先做）✓ 2026-05-14

- [x] 登录 DeepSeek 后台 revoke 旧 key `sk-b5279f...` ✓ 2026-05-14
- [x] 生成新 key ✓ 2026-05-14
- [x] `fetch_report.py:20` 去掉明文 fallback，改为 `os.environ["DEEPSEEK_API_KEY"]` ✓ 2026-05-14
- [x] 在 `~/.zshrc` 设置新 key（dotenv 留给项目 2）✓ 2026-05-14
- [x] 跑一次脚本验证（7 只标的全 OK，DeepSeek 调用 OK，邮件已送达）✓ 2026-05-14

### 2. [x] Git 初始化 + 仓库基础设施 ✓ 2026-05-14

- [x] `git init -b main` ✓ 2026-05-14
- [x] 写 `.gitignore`（含 Python/macOS/编辑器残留/敏感配置/生成报告） ✓ 2026-05-14
- [x] 创建 `.env.example` ✓ 2026-05-14
- [x] 创建 `watchlist.example.json` ✓ 2026-05-14
- [x] `requirements.txt` 加入 `python-dotenv` ✓ 2026-05-14
- [x] `fetch_report.py` 加 `load_dotenv(ROOT / ".env")` ✓ 2026-05-14
- [x] 写本地 `.env`（含真实 key，gitignored） ✓ 2026-05-14
- [x] 首个 commit `2150a37`（amend 自 `058b7e6` 修正作者）✓ 2026-05-14
- [x] git 全局身份设为 `TheGreatCBH <bchen2001@outlook.com>` ✓ 2026-05-14

**冗余**：`DEEPSEEK_API_KEY` 目前同时存在于 `~/.zshrc` 与 `.env`，因 `load_dotenv` 默认不覆盖已存在的环境变量，两者同值时无差异；future-cleanup：可考虑从 `~/.zshrc` 删掉那一行，让 `.env` 成为唯一来源。

### 3. [x] 代码模块化 + prompts 外置 ✓ 2026-05-14

- [x] 按 `daily_report/` 包结构拆分（config / formatting / chart / market_data / news_llm / render_html / notify / pipeline） ✓ 2026-05-14
- [x] 三个 DeepSeek prompts 抽到 `prompts/*.md`，代码用 `.format()` 注入变量 ✓ 2026-05-14
- [x] 入口 `fetch_report.py` 缩成 5 行（保持 cron 向后兼容） ✓ 2026-05-14
- [x] 顺便清掉死代码 `parse_date_str` ✓ 2026-05-14
- [x] 顺便把 `process_news_with_llm` 内硬编码的 watchlist 字符串改成动态 `user_symbols` ✓ 2026-05-14
- [x] 端到端验证通过（7 标的 OK，DeepSeek 3 次调用 OK，邮件已发） ✓ 2026-05-14
- [x] commit `c050f68`（+1087 -1045，15 文件） ✓ 2026-05-14

### 4. [x] Python SMTP 邮件（替代 Mail.app）+ 浅色仪表盘重设计 ✓ 2026-05-14

- [x] 用 `smtplib + email.mime.EmailMessage` 实现发送 ✓ 2026-05-14
- [x] HTML inline 进正文（`add_alternative(..., subtype="html")`），不再用附件 ✓ 2026-05-14
- [x] 配置项进 `.env`：`SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `EMAIL_FROM` ✓ 2026-05-14
- [x] macOS 通知用 `sys.platform == "darwin"` 守卫，无配置/失败时优雅 skip ✓ 2026-05-14
- [x] 删除 `send_email()` 里 AppleScript 实现 ✓ 2026-05-14
- [x] `load_dotenv` 从 `config.py` 提到 `__init__.py`，任意子模块 import 顺序都能读到 env ✓ 2026-05-14
- [x] 解决 SMTP 选型：Outlook personal 已被 Microsoft 切到 OAuth2-only，改用 iCloud SMTP（`smtp.mail.me.com:587` + Apple ID 应用密码）✓ 2026-05-14
- [x] Email-safe CSS 修复：CSS 变量 `var(--xxx)` 替换为字面 hex，Outlook iOS 才能正确渲染颜色/背景 ✓ 2026-05-14
- [x] 浅色仪表盘重设计：冷调底色 `#f4f6f9` + 白卡 + 暖金 accent + 油墨绿/暗红涨跌色 ✓ 2026-05-14
- [x] `chart.py`：matplotlib 配色全换（白底、林木绿/暗红），尺寸放大至 `figsize=(6.6, 2.5)`、`fontsize=9` ✓ 2026-05-14
- [x] 修复 iOS Outlook 不支持 `flex gap`：`sc-info` / `sc-changes` 改用 `display: inline-block; margin-right` ✓ 2026-05-14
- [x] `<details>/<summary>` 替换为普通 div（邮件客户端反正不支持折叠）✓ 2026-05-14
- [x] 端到端验证通过（真实数据 7 标的 OK，邮件渲染正确）✓ 2026-05-14
- [x] commit `3ef28d2`（SMTP + email-safe CSS）+ `37f951f`（浅色重设计）✓ 2026-05-14

### 5. [ ] A 股 / H 股支持

- [ ] `requirements.txt` 加入 `akshare`
- [ ] `watchlist.json` 增加 `market` 字段约定（A / H / US）以及对应 yfinance 后缀映射
- [ ] 行情：A 股 `.SS`/`.SZ`、港股 `.HK`，仍走 yfinance
- [ ] 新闻：A/H 股接 akshare（接口待选）
- [ ] LLM prompt 兼容中文新闻输入（其实当前 prompt 已是中文，主要验证）

### 6. [ ] README

- [ ] 项目介绍 + 报告效果截图
- [ ] 安装 / 配置 / 运行
- [ ] 自定义 watchlist 说明
- [ ] 邮件 SMTP 配置说明（Gmail / Outlook 应用密码教程链接）
- [ ] cron 调度示例
- [ ] 开源协议（MIT / Apache 2.0 选一）

### 7. [ ] （可选 / 低优先）Windows + 英文 i18n

- [ ] 通知跨平台化（`plyer` 或条件分支）
- [ ] HTML 文案抽 i18n 字典（zh-CN / en-US）
- [ ] `prompts/` 增加 `en/` 镜像
- [ ] README 双语

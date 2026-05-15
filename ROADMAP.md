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
- [x] A/H 股方案：A+ 混合 —— A 股行情/新闻全 akshare（Sina 日线 + EastMoney 新闻），港股 yfinance 行情 + akshare 新闻 ✓ 2026-05-14
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

### 5. [x] A 股 / H 股支持（A+ 混合方案）✓ 2026-05-14

- [x] `requirements.txt` 加入 `akshare>=1.18.0` ✓ 2026-05-14
- [x] 切到项目本地 venv `.venv/`，launchd plist 指向 `.venv/bin/python3` ✓ 2026-05-14
- [x] 清理 system Python `--user` site-packages 里项目特定的 32 个包，保留 Jupyter/数据科学栈 ✓ 2026-05-14
- [x] `market_data.fetch_ticker` 增加 dispatcher：按 `.SS/.SZ/.HK/.TO` 后缀路由到 yfinance / akshare ✓ 2026-05-14
- [x] `market_data_cn.py`：A 股完整 fetch（Sina 日线 + EastMoney 新闻；market_cap 由 outstanding_share × close 计算）+ 港股新闻补强 ✓ 2026-05-14
- [x] 多币种支持：`currency_symbol` 字段（$/HK$/¥/C$），`fmt_price` 和 `nm` 接受 currency 参数 ✓ 2026-05-14
- [x] `render_html._primary_secondary`：A/H 股以名称为主、代号为副；美股反之 ✓ 2026-05-14
- [x] watchlist `name` 字段升级为名称主源（覆盖 yfinance longName，让中文别名生效）✓ 2026-05-14
- [x] `watchlist.example.json` 增加 600519.SS / 000001.SZ / 0700.HK 示例 ✓ 2026-05-14
- [x] 端到端 mock 验证通过（真实茅台/平安/腾讯行情 + 中文新闻 + iOS 渲染）✓ 2026-05-14
- [x] commit `d87b97c`（+282 -33，9 文件）✓ 2026-05-14

### 6. [x] README ✓ 2026-05-14

- [x] 英文主版 `README.md`：feature 列表、依赖、安装、配置（`.env` + `watchlist.json` 多市场示例）、运行、launchd 调度示例、架构表、已知限制、协议、致谢 ✓ 2026-05-14
- [x] 中文镜像 `README.zh-CN.md` ✓ 2026-05-14
- [x] `LICENSE`：MIT，2026 TheGreatCBH ✓ 2026-05-14
- [x] `examples/com.investment.daily-report.plist`：脱敏 launchd 模板（REPO_PATH 占位）✓ 2026-05-14
- [x] Outlook personal OAuth2-only 的坑、Microsoft 不可用、iCloud 推荐路径写进 README ✓ 2026-05-14
- [ ] 报告效果截图（暂不放，后续随时补）
- [x] commit `3c257d0`（+366 -8，6 文件）✓ 2026-05-14
- [x] **push 到 GitHub public repo**：https://github.com/TheGreatCBH/daily-investment-report ✓ 2026-05-14

### 7. [x] Windows + 英文 i18n ✓ 2026-05-15

- [x] 通知跨平台化（无新增依赖，按 `sys.platform` 条件分派：macOS osascript / Linux notify-send / Windows PowerShell toast / 其他 no-op）✓ 2026-05-15
- [x] HTML 文案 i18n：`daily_report/i18n.py` 集中 `_STRINGS` + `t()` helper，环境变量 `REPORT_LOCALE` 切换（默认 `zh-CN`，支持 `en-US`）✓ 2026-05-15
- [x] `prompts/` 增加 `en/` 镜像（highlights / stock_analysis / translate_titles），news_llm 按 locale 加载 ✓ 2026-05-15
- [x] formatting / market_data_cn / pipeline / render_html / notify 所有用户可见字面量替换为 `t()` 调用 ✓ 2026-05-15
- [x] README 双语已在项目 6 完成 ✓ 2026-05-14
- [x] CLAUDE.md / README / `.env.example` 文档化 `REPORT_LOCALE` ✓ 2026-05-15
- [x] 烟测验证：zh-CN 默认 + en-US 切换两个 locale 都正确渲染，无字符串泄漏 ✓ 2026-05-15
- [x] commit `3a19ae8`（13 文件，含 3 个英文 prompts）✓ 2026-05-15

---

## Code Review 修复（2026-05-15）

### 8. [~] Code review important 修复

- [x] `tests/test_basics.py`：18 个最小单元测试（`_detect_market` / `fmt_change` / `nm` / `_primary_secondary`，无网络依赖）✓ 2026-05-15
- [x] `config.py` KeyError → RuntimeError + 友好提示（含 .env 配置步骤）✓ 2026-05-15
- [x] `notify.py` AppleScript `_esc_as()` + PowerShell `_esc_ps()` 转义，消除注入形态 ✓ 2026-05-15
- [x] `news_llm._extract_json`：先 try 直接 `json.loads`，失败再剥围栏，提升容错 ✓ 2026-05-15
- [x] `requirements.txt` `>=` → `~=` 锁主版本 + 加入 `pytest~=8.0` ✓ 2026-05-15
- [x] 网络调用加 retry / backoff（`_retry` 手撸线性退避，pipeline + news_llm 各 3 次重试）✓ 2026-05-15
- [x] `pipeline.py` / `notify.py` / `news_llm.py` `print` → `logging`（`basicConfig` 在 `pipeline.main()` 里初始化）✓ 2026-05-15
- [x] `market_data.py` `df_month` 重命名 → `df_1mo` + 交易日近似注释；`market_data_cn.py` 252/22/6 同步注释 ✓ 2026-05-15
- [x] A 股 PE：`pe_ratio` 为 None 时 HTML 不渲染该行（不再显示 "PE -"）✓ 2026-05-15
- [ ] README 加报告效果截图

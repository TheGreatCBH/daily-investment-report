# 项目演进路线

记录这个项目从"个人原型脚本"演进到"公开 GitHub 仓库"的所有改造项与执行进度。每完成一项请勾选并写上完成日期。

## 状态约定

- `- [ ]` 待做
- `- [~]` 进行中
- `- [x]` 已完成 ✓ YYYY-MM-DD

---

## 待决策事项（动工前确认）

讨论于 2026-05-14，以下选项尚未拍板，开工时需要先选定：

- [ ] `watchlist.json` 含真实邮箱 `bchen2001@outlook.com` —— public 仓库要不要保留？（建议拆 `watchlist.example.json` + `.gitignore` 真实文件）
- [ ] `.claude/settings.local.json` 要不要 commit？
- [ ] `reports/` 历史报告要不要清掉？
- [ ] 模块化包名用 `src/` 还是 `daily_report/`？
- [ ] HTML 的 CSS 要不要外置成 `templates/report.html` + `static/style.css`？
- [ ] A/H 股新闻方案：A（yfinance 行情 + akshare 新闻）/ B（全 akshare）/ C（DeepSeek 联网搜索）？
- [ ] 邮件 SMTP 通道：Gmail / Outlook / QQ-163 / 第三方 API（SendGrid / Resend）？

---

## 执行清单

### 1. [x] 处理已泄露的 DeepSeek API Key（紧急·必须最先做）✓ 2026-05-14

- [x] 登录 DeepSeek 后台 revoke 旧 key `sk-b5279f...` ✓ 2026-05-14
- [x] 生成新 key ✓ 2026-05-14
- [x] `fetch_report.py:20` 去掉明文 fallback，改为 `os.environ["DEEPSEEK_API_KEY"]` ✓ 2026-05-14
- [x] 在 `~/.zshrc` 设置新 key（dotenv 留给项目 2）✓ 2026-05-14
- [x] 跑一次脚本验证（7 只标的全 OK，DeepSeek 调用 OK，邮件已送达）✓ 2026-05-14

### 2. [ ] Git 初始化 + 仓库基础设施

- [ ] `git init`
- [ ] 写 `.gitignore`（含 `__pycache__/`、`.DS_Store`、`.Rhistory`、`.chartjs.cache`、`reports/*.html`、`reports/*.log`、`.env`，可能含 `watchlist.json`）
- [ ] 创建 `.env.example`
- [ ] （视决策）创建 `watchlist.example.json`
- [ ] `requirements.txt` 加入 `python-dotenv`
- [ ] 代码用 `dotenv.load_dotenv()` 加载 `.env`
- [ ] 首个 commit

### 3. [ ] 代码模块化 + prompts 外置

- [ ] 按议定的目录结构拆分（包名待定）
  - `config.py` / `market_data.py` / `news_llm.py` / `chart.py` / `render_html.py` / `notify.py`
- [ ] 三个 DeepSeek prompts 抽到 `prompts/*.md`，代码用 `.format()` 注入变量
- [ ] 入口 `fetch_report.py` 只剩 `main()` 流程编排
- [ ] 验证：跑一次完整流程，对比报告 HTML 输出与重构前等价

### 4. [ ] Python SMTP 邮件（替代 Mail.app）

- [ ] 用 `smtplib + email.mime.multipart` 实现发送
- [ ] HTML inline 进正文（不再用附件形式）
- [ ] 配置项进 `.env`：`SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `EMAIL_FROM`
- [ ] macOS 通知保留，无配置/失败时优雅 skip
- [ ] 删除 `send_email()` 里 AppleScript 实现

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

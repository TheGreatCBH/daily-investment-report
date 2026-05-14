# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

每日投资简报生成器：从 Yahoo Finance 拉取持仓行情与新闻，调用 DeepSeek API 完成中文翻译/解读/重要性排序，渲染成 HTML 报告，通过 SMTP 发送邮件（HTML inline 进正文），并在 macOS 上发系统通知。

代码组织为 `daily_report/` Python 包；`fetch_report.py` 是仅 5 行的入口（保持向后兼容现有 cron）。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 设置 DeepSeek API Key（脚本中有 hardcode 兜底，但生产环境应通过环境变量传入）
export DEEPSEEK_API_KEY="sk-..."

# 生成今日报告（一次完整跑通：拉数据 → LLM 处理 → HTML → 通知 + 邮件）
python fetch_report.py
```

报告产物写入 `reports/daily_report_YYYY-MM-DD.html`（带 UTF-8 BOM，邮件附件由 Mail.app 发送）。`reports/cron.log` 与 `reports/cron_error.log` 表明该脚本由 cron 定时调度。

## 架构要点

**包结构**：

```
fetch_report.py                # 5 行入口，launchd 调用此文件
daily_report/
  config.py                    # ROOT/paths/DEEPSEEK_API_KEY/load_config
  __init__.py                  # 包级 load_dotenv(.env)
  formatting.py                # fmt_change / fmt_price(currency) / nm(currency) / volume_badge
  i18n.py                      # REPORT_LOCALE 环境变量 + _STRINGS 字典 + t() helper
  chart.py                     # render_chart_png（matplotlib → base64 PNG，浅色仪表盘配色）
  market_data.py               # fetch_ticker 入口 + yfinance 分支 + 市场路由 + _CURRENCY
  market_data_cn.py            # akshare 分支：A 股完整 fetch + 港股新闻补强
  news_llm.py                  # 三个 DeepSeek 调用 + _client / _load_prompt / _extract_json
  render_html.py               # generate_html + _render_* + _primary_secondary（A/H 名称为主）
  notify.py                    # send_notification 跨平台（macOS/Linux/Windows，其余 no-op）+ send_email（SMTP）
  pipeline.py                  # main() 流程编排
prompts/
  highlights.md                # process_news_with_llm 的 prompt，占位符 {items_json} {user_symbols}
  stock_analysis.md            # summarize_stock_news 的 prompt，{symbol} {name} {description} {items_json} {items_len}
  translate_titles.md          # translate_news_titles 的 prompt，{titles_list}
  en/                          # 英文 prompts 镜像，REPORT_LOCALE=en-US 时加载
.venv/                         # 项目专用 Python 虚拟环境（gitignored），launchd 直接用 .venv/bin/python3
examples/
  com.investment.daily-report.plist  # launchd 模板（脱敏，含 REPO_PATH 占位符）
README.md                      # public README（英文主版）
README.zh-CN.md                # 中文镜像
LICENSE                        # MIT
```

**数据流（`pipeline.main()` 顺序执行）**：

1. `load_config()` 读取 `watchlist.json` —— 包含收件邮箱与标的列表。每个标的可选 `search_terms` 与 `description` 字段；带 `search_terms` 的（一般是 ETF）走关键词搜索新闻路径，不带的走 `Ticker.news`。
2. `fetch_macro_news()` 用 `^GSPC` 拉取宏观大盘新闻。
3. 对 watchlist 中每个标的执行 `fetch_ticker()`：行情、日/周/月涨跌、日内 5 分钟走势、PE/市值/52w 极值等指标，以及标的相关新闻（去重 + 按周一 3 天 / 平日 1 天的窗口过滤）。
4. `process_news_with_llm()` 把所有新闻一次性丢给 DeepSeek，让它翻译标题、写 100-150 字摘要、跨宏观/个股按重要性排序，保留 10-15 条作为「今日要闻」。`user_symbols` 由 watchlist 动态拼出（不再硬编码）。
5. `translate_news_titles()` 批量翻译每只标的卡片底部的新闻标题。
6. `summarize_stock_news()` 按股票批量调用 LLM，为每条新闻生成 200-300 字中文解读；对 ETF 标的，若 LLM 判定新闻不相关（`analysis == "IRRELEVANT"`），会做关键词兜底（黄金类用 `gold/mining/bullion/...`；加拿大银行类用 `bank/tsx/bmo/...`）防止被误删。
7. `render_chart_png()` 用 matplotlib 把日内走势生成 PNG，再以 base64 内嵌进 HTML（关键：邮件附件场景下不能依赖外链图）。
8. `generate_html()` + `_render_*` 系列函数拼装最终 HTML。样式高度自定义（深色主题、CSS 变量集中在 `:root`）。
9. `send_notification()` 在 macOS 上用 `osascript display notification` 发系统通知，非 macOS 静默 skip；`send_email()` 用 `smtplib + email.mime.EmailMessage`，HTML 通过 `add_alternative(..., subtype="html")` 内嵌进正文（不再是附件）。

**多市场数据源路由**：`market_data.fetch_ticker()` 按 yfinance 风格 symbol 后缀分派：
- `.SS` / `.SZ`（A 股）：行情 + 元数据 + 新闻全部走 akshare（`market_data_cn.fetch_a_share`）。日线/分钟线用 Sina 后端，新闻用东方财富 `stock_news_em`。市值由 `outstanding_share × close` 算出。东方财富的 quote 接口偶发被 IP 限流，所以日线刻意走 Sina，新闻接口（不同 endpoint）通常不受影响。
- `.HK`（港股）：行情走 yfinance，但新闻被 akshare 的 `stock_news_em(symbol="00700")` 中文新闻**覆盖**掉（yfinance 港股新闻基本是英文稀疏数据，可用性差）。
- 其它（默认 US）：完整走 yfinance。

`watchlist.json` 里用户填写的 `name` 字段是名称的**主源**（覆盖 yfinance 的 longName），允许把 "Tencent Holdings Limited" 显示为"腾讯控股"。`render_html._primary_secondary` 在标的为 A/H 股（纯数字代号）时把名称作为主显示、代号作为副显示；美股反之。

`fetch_ticker` 返回的 dict 含 `currency_symbol` 字段（US 是 `$`、HK 是 `HK$`、A 股是 `¥`、TSX 是 `C$`），`formatting.fmt_price` 与 `nm` 接受 currency 参数。

**LLM 调用规范**：所有 DeepSeek 调用走 `news_llm._client()` 工厂（`OpenAI(base_url="https://api.deepseek.com")`）+ `deepseek-chat` 模型，温度区分用途（翻译 0.1、解读 0.5、要闻排序 0.3）。响应文本统一过 `_extract_json()` 剥围栏再解析。

**SMTP 调用规范**：`send_email()` 从环境变量读 `SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / EMAIL_FROM`。当前生产用 iCloud (`smtp.mail.me.com:587`)；Microsoft 个人 Outlook.com 账号已被切到 OAuth2-only，basic SMTP auth 不再可用，所以不要尝试。

**Prompt 模板**：prompts 文件用 Python `.format()` 占位符，JSON 示例中的字面 `{ }` 必须写作 `{{ }}`（这是 `.format()` 的转义约定）。

**Env 加载**：`.env` 在 `daily_report/__init__.py` 包导入时一次性加载，子模块任意 import 顺序都读得到环境变量。

**i18n / 多语言**：通过环境变量 `REPORT_LOCALE` 切换报告语言，默认 `zh-CN`，支持 `en-US`。所有面向用户可见的 HTML/邮件/通知字面量集中在 `daily_report/i18n.py` 的 `_STRINGS` 字典里，代码通过 `t("key", **kwargs)` 取值。LLM prompts 走文件级 i18n：`prompts/en/` 镜像若存在则在 en-US 下加载，否则回退到 `prompts/`（默认中文）。**注意**：`i18n.LOCALE` 在模块 import 时定型，运行中改环境变量不生效，需要重启进程。

**Email-safe CSS 约束**：HTML 通过邮件发送时由 Outlook for iOS / Apple Mail 渲染，**禁止使用 CSS 变量**（`var(--xxx)` 不被解析），所有颜色必须以字面 hex / rgba 值出现在 `<style>` 块中。`<details>/<summary>` 在邮件客户端里无法折叠，相当于普通 div。`flex` 的 `gap` 属性在 iOS Outlook 不支持，多个 inline 元素之间的间距用 `display: inline-block; margin-right: Npx` 实现。

**平台依赖**：邮件发送（SMTP）跨平台。通知（`send_notification`）分派：macOS 走 `osascript`、Linux 走 `notify-send`、Windows 走 PowerShell toast（Win10+），其余平台 silent no-op。`matplotlib.use("Agg")` 是显式声明用无头后端，不要改。

## 修改提示

- 新增标的：编辑 `watchlist.json`。ETF 类务必填 `search_terms`，否则 `Ticker.news` 大概率为空。
- 调整新闻数量/窗口：`market_data.fetch_ticker()` 内 `max_age_days` 与 `[:5]`、`search_news(..., max_results=4)` 控制总量；`prompts/highlights.md` 的「保留 10-15 条」要同步。
- 改 HTML 样式：CSS 集中在 `render_html.generate_html()` 的 `<style>` 块（移动端断点 `@media (max-width: 480px)`）。
- 改 prompt：编辑 `prompts/*.md`；如要新增占位符，同步更新 `news_llm.py` 里对应函数的 `.format()` 调用。
- 不要把 `DEEPSEEK_API_KEY` 的兜底值写回 `config.py`，密钥来源永远是 `.env` 或环境变量。

## 任务进度跟踪

本项目用根目录的 `ROADMAP.md` 维护改造路线与进度。**每完成一项任务或子任务后，立即编辑 `ROADMAP.md`**：把对应的 `- [ ]` 改为 `- [x] ... ✓ YYYY-MM-DD`。如果讨论中产生了新的待办、决策项或推翻了原计划，也要同步写回 `ROADMAP.md`，不要只留在对话里 —— 跨会话只有 `ROADMAP.md` 是权威。

## 注意事项

回复语言使用中文。

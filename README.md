# Daily Investment Report

A personal morning brief generator. Pulls watchlist quotes from Yahoo Finance and akshare, summarizes overnight news with an LLM, ranks by importance to your holdings, renders a clean HTML email, and delivers it.

> 中文版：[README.zh-CN.md](README.zh-CN.md)

<p align="center">
  <img src="docs/sample_report.png" alt="Sample report" width="420">
  <br>
  <em>Sample report (top section) generated from the example watchlist.</em>
</p>

## Features

- **Multi-market in one watchlist**: US (NYSE/NASDAQ via yfinance), Hong Kong, and A-shares (Shanghai/Shenzhen via akshare).
- **LLM-curated highlights**: each morning's news (macro + per-stock) translated to Chinese, ranked by importance for *your* holdings, top 10–15 items only.
- **Per-stock interpretation**: 200–300 word commentary on every relevant news item, separating short-term and long-term impact.
- **Email-safe HTML**: light cool-toned dashboard, inline base64 charts, no CSS variables — renders correctly in iOS Mail and Outlook for iOS without falling back to default styles.
- **Scheduled**: macOS `launchd` every day at 09:00 (sample plist included), with native system notification on completion.
- **One-click manual run**: double-click `run_report.command` in Finder to trigger a report on demand, without waiting for the schedule.

## Requirements

- Python 3.9+
- An SMTP-capable email account
  - **iCloud** (recommended): use an [app-specific password](https://appleid.apple.com)
  - **Gmail**: enable 2FA and create an app password
  - **Microsoft personal Outlook accounts no longer work** — Microsoft moved them to OAuth2-only auth, and basic SMTP (including app passwords) is server-side blocked
- An API key for any **OpenAI-compatible LLM**: [DeepSeek](https://platform.deepseek.com) (default, cheap), [OpenAI](https://platform.openai.com), [Groq](https://console.groq.com), or a local [Ollama](https://ollama.com) instance — configured via `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` in `.env`

## Install

```bash
git clone https://github.com/TheGreatCBH/daily-investment-report.git
cd daily-investment-report
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Configure

```bash
cp .env.example .env
cp watchlist.example.json watchlist.json
```

Edit `.env`:

```
# LLM — any OpenAI-compatible endpoint
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.deepseek.com   # leave empty for OpenAI; omit to keep DeepSeek default
LLM_MODEL=deepseek-chat                 # e.g. gpt-4o, llama-3.3-70b-versatile, qwen2.5:7b

SMTP_HOST=smtp.mail.me.com
SMTP_PORT=587
SMTP_USER=you@icloud.com
SMTP_PASS=xxxx-xxxx-xxxx-xxxx
EMAIL_FROM=you@icloud.com

# Optional: report language. Default zh-CN; set to en-US for English output.
# REPORT_LOCALE=en-US
```

For iCloud, the `From:` address must equal your iCloud account or a verified alias.

`REPORT_LOCALE` switches the entire output: HTML labels, email subject, OS notification text, and the language of LLM-generated summaries (English prompts live under `prompts/en/`).

Edit `watchlist.json` with your holdings. Symbol convention follows yfinance:

| Market | Symbol example | Notes |
|---|---|---|
| US stock | `NVDA`, `AAPL` | No suffix |
| US ETF | `IAU` | Add `search_terms` to widen news coverage |
| Toronto | `ZEB.TO` | `.TO` / `.V` |
| Hong Kong | `0700.HK` | `.HK`; news comes from akshare in Chinese |
| Shanghai A | `600519.SS` | `.SS`; everything via akshare |
| Shenzhen A | `000001.SZ` | `.SZ`; everything via akshare |

```json
{
  "email": { "address": "you@example.com" },
  "watchlist": [
    { "symbol": "NVDA",       "name": "NVIDIA",      "market": "NASDAQ", "type": "stock" },
    { "symbol": "600519.SS",  "name": "贵州茅台",     "market": "SH",     "type": "stock" },
    { "symbol": "0700.HK",    "name": "腾讯控股",     "market": "HK",     "type": "stock" }
  ]
}
```

The `name` field you write is the authoritative display name — it overrides any auto-discovered name from yfinance / akshare. So you can write "腾讯控股" instead of "Tencent Holdings Limited".

## Run

```bash
.venv/bin/python fetch_report.py
```

On macOS you can also just **double-click `run_report.command`** in Finder to run it once on demand (drag it to the Dock or Desktop for a one-click shortcut). It runs the same pipeline and opens a Terminal window showing progress.

This will:
1. Pull S&P 500 macro news + per-stock quotes and news
2. Call DeepSeek three times (highlights ranking, title translation, per-stock interpretation)
3. Render HTML to `reports/daily_report_YYYY-MM-DD.html`
4. Send the HTML by SMTP, inline in the message body
5. Post a macOS notification (skipped silently on other platforms)

> Tip: set `WATCHLIST_PATH=/path/to/other.json` to run against an alternate watchlist (e.g. a sanitized demo) without touching your real `watchlist.json`.

## Schedule (macOS launchd)

```bash
# 1. Edit the example plist and replace REPO_PATH with your absolute repo path
sed "s|REPO_PATH|$(pwd)|g" examples/com.investment.daily-report.plist \
  > ~/Library/LaunchAgents/com.investment.daily-report.plist

# 2. Load it
launchctl load ~/Library/LaunchAgents/com.investment.daily-report.plist
```

The default schedule fires every day at 09:00 local time. To run on weekdays only, split `StartCalendarInterval` into five dicts with `Weekday` 1–5 (a commented hint is in the plist).

To reload after editing the schedule:

```bash
launchctl bootout gui/$(id -u)/com.investment.daily-report 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.investment.daily-report.plist
```

For Linux / cron (every day at 09:00):

```cron
0 9 * * * cd /path/to/daily-investment-report && .venv/bin/python fetch_report.py >> reports/cron.log 2>> reports/cron_error.log
```

## Architecture

`fetch_report.py` is a 5-line entry point. Real code lives in `daily_report/`:

| Module | Responsibility |
|---|---|
| `market_data.py` | yfinance fetch + dispatcher (routes by symbol suffix to akshare for A/HK) |
| `market_data_cn.py` | akshare fetch for A-shares (quotes + news) and HK news supplementation |
| `news_llm.py` | DeepSeek calls; prompts externalized to `prompts/*.md` |
| `render_html.py` | Light cool-toned dashboard, email-safe CSS, currency-aware rendering |
| `chart.py` | matplotlib → base64 PNG charts |
| `notify.py` | SMTP email + macOS osascript notification |
| `pipeline.py` | `main()` orchestration |

See [CLAUDE.md](CLAUDE.md) for the deeper architectural conventions (prompt templating, email-safe CSS rules, env loading order, multi-market routing).

## Limitations

- **Cross-platform notifications are best-effort.** macOS uses `osascript`, Linux uses `notify-send` (requires `libnotify-bin`), Windows uses a PowerShell-based toast on Win10+. Other platforms silently skip. Email is fully cross-platform via SMTP.
- **No Microsoft personal Outlook outbound.** They moved to OAuth2-only.
- **akshare EastMoney quote endpoints rate-limit on heavy use.** We use Sina for A-share daily data as the primary source; news endpoints have been stable.
- **HTML email size ~150–180KB with 7 stocks.** Most clients render fine; Gmail web clips emails over ~102KB and adds a "View entire message" link.

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

- [yfinance](https://github.com/ranaroussi/yfinance) — US/HK/global equity data and news
- [akshare](https://github.com/akfamily/akshare) — A-share quotes and Chinese news coverage
- [DeepSeek](https://www.deepseek.com/) — affordable Chinese-tuned LLM with OpenAI-compatible API
- [matplotlib](https://matplotlib.org/) — chart rendering

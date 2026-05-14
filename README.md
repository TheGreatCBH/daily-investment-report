# Daily Investment Report

A personal morning brief generator. Pulls watchlist quotes from Yahoo Finance and akshare, summarizes overnight news with an LLM, ranks by importance to your holdings, renders a clean HTML email, and delivers it.

> 中文版：[README.zh-CN.md](README.zh-CN.md)

## Features

- **Multi-market in one watchlist**: US (NYSE/NASDAQ via yfinance), Hong Kong, and A-shares (Shanghai/Shenzhen via akshare).
- **LLM-curated highlights**: each morning's news (macro + per-stock) translated to Chinese, ranked by importance for *your* holdings, top 10–15 items only.
- **Per-stock interpretation**: 200–300 word commentary on every relevant news item, separating short-term and long-term impact.
- **Email-safe HTML**: light cool-toned dashboard, inline base64 charts, no CSS variables — renders correctly in iOS Mail and Outlook for iOS without falling back to default styles.
- **Scheduled**: macOS `launchd` weekday 09:30 (sample plist included), with native system notification on completion.

## Requirements

- Python 3.9+
- An SMTP-capable email account
  - **iCloud** (recommended): use an [app-specific password](https://appleid.apple.com)
  - **Gmail**: enable 2FA and create an app password
  - **Microsoft personal Outlook accounts no longer work** — Microsoft moved them to OAuth2-only auth, and basic SMTP (including app passwords) is server-side blocked
- A [DeepSeek API key](https://platform.deepseek.com) (the LLM is reached via the `openai` SDK with a custom `base_url`; any OpenAI-compatible endpoint also works with a one-line change in `daily_report/news_llm.py`)

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
DEEPSEEK_API_KEY=sk-...

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

This will:
1. Pull S&P 500 macro news + per-stock quotes and news
2. Call DeepSeek three times (highlights ranking, title translation, per-stock interpretation)
3. Render HTML to `reports/daily_report_YYYY-MM-DD.html`
4. Send the HTML by SMTP, inline in the message body
5. Post a macOS notification (skipped silently on other platforms)

## Schedule (macOS launchd)

```bash
# 1. Edit the example plist and replace REPO_PATH with your absolute repo path
sed "s|REPO_PATH|$(pwd)|g" examples/com.investment.daily-report.plist \
  > ~/Library/LaunchAgents/com.investment.daily-report.plist

# 2. Load it
launchctl load ~/Library/LaunchAgents/com.investment.daily-report.plist
```

The default schedule fires at 09:30 China time on weekdays (after the US after-hours session closes), which is when intraday US chart data is most complete.

For Linux / cron:

```cron
30 9 * * 1-5 cd /path/to/daily-investment-report && .venv/bin/python fetch_report.py >> reports/cron.log 2>> reports/cron_error.log
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

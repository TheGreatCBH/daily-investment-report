import json

from openai import OpenAI

from .config import DEEPSEEK_API_KEY, PROMPTS_DIR


def _client():
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")


def _load_prompt(name):
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _extract_json(text):
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


def process_news_with_llm(macro_news, all_data):
    all_items = []
    for n in macro_news:
        all_items.append({"type": "macro", "title": n["title"], "publisher": n["publisher"]})
    for d in all_data:
        for n in d["news"]:
            all_items.append({
                "type": "stock", "symbol": d["symbol"], "name": d["name"],
                "title": n["title"], "publisher": n["publisher"],
            })

    if not all_items:
        return {"highlights": [], "macro_news": []}

    items_json = json.dumps(all_items, ensure_ascii=False, indent=2)
    user_symbols = " ".join(d["symbol"] for d in all_data)
    prompt = _load_prompt("highlights.md").format(
        items_json=items_json,
        user_symbols=user_symbols,
    )

    try:
        resp = _client().chat.completions.create(
            model="deepseek-chat",
            max_tokens=8192,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        return _extract_json(resp.choices[0].message.content)
    except Exception as e:
        print(f"  [WARN] DeepSeek API 调用失败: {e}")
        return None


def summarize_stock_news(all_data):
    """为每只股票的每条新闻生成详细中文解读，按股票批量调用。
    返回 (summaries_dict, irrelevant_titles_set)"""
    all_summaries = {}
    irrelevant_titles = set()
    client = _client()
    template = _load_prompt("stock_analysis.md")

    for d in all_data:
        if not d["news"]:
            continue
        items = [{"title": n["title"], "summary": n.get("summary", "")} for n in d["news"]]
        items_json = json.dumps(items, ensure_ascii=False, indent=2)
        prompt = template.format(
            symbol=d["symbol"],
            name=d["name"],
            description=d.get("description", ""),
            items_json=items_json,
            items_len=len(items),
        )

        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                max_tokens=4096,
                temperature=0.5,
                messages=[{"role": "user", "content": prompt}],
            )
            data = _extract_json(resp.choices[0].message.content)
            for item in data.get("items", []):
                title = item.get("title", "")
                analysis = (item.get("analysis") or item.get("summary_cn") or
                            item.get("content") or item.get("解读") or item.get("text") or "")
                if analysis and "IRRELEVANT" in analysis.upper():
                    # 关键词兜底：ETF 标的搜索结果含底层资产关键词 → 强制保留
                    keep_by_kw = False
                    if d.get("search_terms"):
                        title_lower = title.lower()
                        asset_kw = {"gold", "mining", "bullion", "precious", "bank", "canadian",
                                    "tsx", "financial", "bmo", "rbc", "td", "scotiabank",
                                    "cibc", "wealth", "asset", "etf"}
                        keep_by_kw = any(kw in title_lower for kw in asset_kw)
                    if not keep_by_kw:
                        irrelevant_titles.add(title)
                        continue
                    analysis = "暂无详细解读"
                if title and analysis:
                    all_summaries[title] = analysis
                elif title:
                    all_summaries[title] = "暂无详细解读"
        except Exception as e:
            print(f"    {d['symbol']} 新闻解读失败: {e}")

    return all_summaries, irrelevant_titles


def translate_news_titles(all_data):
    """批量翻译个股新闻标题为中文"""
    titles_map = {}
    for d in all_data:
        for n in d["news"]:
            key = f"{d['symbol']}::{n['title'][:100]}"
            titles_map[key] = n["title"]

    if not titles_map:
        return {}

    titles_list = "\n".join(f"- {v}" for v in titles_map.values())
    prompt = _load_prompt("translate_titles.md").format(titles_list=titles_list)

    try:
        resp = _client().chat.completions.create(
            model="deepseek-chat",
            max_tokens=2048,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        data = _extract_json(resp.choices[0].message.content)
        return {t["original"]: t["translated"] for t in data.get("translations", [])}
    except Exception as e:
        print(f"失败: {e}")
        return {}

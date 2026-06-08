import json
import logging

from openai import OpenAI

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, PROMPTS_DIR
from .i18n import LOCALE
from .utils import retry

logger = logging.getLogger(__name__)


def _client():
    kwargs = {"api_key": LLM_API_KEY}
    if LLM_BASE_URL:
        kwargs["base_url"] = LLM_BASE_URL
    return OpenAI(**kwargs)


def _load_prompt(name):
    """en-US locale 优先从 prompts/en/ 加载；缺失则回退到 prompts/（默认中文）。"""
    if LOCALE == "en-US":
        en_path = PROMPTS_DIR / "en" / name
        if en_path.exists():
            return en_path.read_text(encoding="utf-8")
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _extract_json(text):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```")[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```")[0]
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
        return {"macro_highlights": [], "stock_highlights": []}

    items_json = json.dumps(all_items, ensure_ascii=False, indent=2)
    user_symbols = " ".join(d["symbol"] for d in all_data)
    prompt = _load_prompt("highlights.md").format(
        items_json=items_json,
        user_symbols=user_symbols,
    )

    client = _client()
    try:
        resp = retry(
            lambda: client.chat.completions.create(
                model=LLM_MODEL,
                max_tokens=8192,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            ),
            label="highlights",
        )
        return _extract_json(resp.choices[0].message.content)
    except Exception as e:
        logger.warning("LLM highlights 调用失败: %s", e)
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
            resp = retry(
                lambda p=prompt: client.chat.completions.create(
                    model=LLM_MODEL,
                    max_tokens=4096,
                    temperature=0.5,
                    messages=[{"role": "user", "content": p}],
                ),
                label=d["symbol"],
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
            logger.warning("  %s 新闻解读失败: %s", d["symbol"], e)

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

    client = _client()
    try:
        resp = retry(
            lambda: client.chat.completions.create(
                model=LLM_MODEL,
                max_tokens=2048,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            ),
            label="translate_titles",
        )
        data = _extract_json(resp.choices[0].message.content)
        return {t["original"]: t["translated"] for t in data.get("translations", [])}
    except Exception as e:
        logger.warning("标题翻译失败: %s", e)
        return {}

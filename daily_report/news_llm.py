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


# 每批翻译的标题上限：标的变多时分批调用，避免单次 LLM 输出撞 max_tokens 上限被截断
# （DeepSeek deepseek-chat 输出上限 ~8192 tokens，与 context 窗口是两码事）。
_TRANSLATE_BATCH_SIZE = 15


def _translate_titles_batch(client, template, titles):
    """翻译一批标题，返回 {original: translated}。单批失败抛异常，由调用方兜底记日志。"""
    titles_list = "\n".join(f"- {v}" for v in titles)
    prompt = template.format(titles_list=titles_list)
    resp = retry(
        lambda: client.chat.completions.create(
            model=LLM_MODEL,
            max_tokens=8192,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        ),
        label="translate_titles",
    )
    data = _extract_json(resp.choices[0].message.content)
    return {t["original"]: t["translated"] for t in data.get("translations", [])}


def translate_news_titles(all_data):
    """批量翻译个股新闻标题为中文；按 _TRANSLATE_BATCH_SIZE 分批调用。

    分批目的：标的变多后单次输出会撞 max_tokens 上限、JSON 被截断解析失败（历史上整份翻译归零）。
    分批后每批输出可控，且单批失败只丢那一批、其余批次照常返回（partial 优于全 None）。
    """
    # 按完整 title 去重（render 消费时以完整 title 为 key，见 render_html 的 news_translations.get(title)）
    titles = []
    seen = set()
    for d in all_data:
        for n in d["news"]:
            title = n["title"]
            if title not in seen:
                seen.add(title)
                titles.append(title)

    if not titles:
        return {}

    client = _client()
    template = _load_prompt("translate_titles.md")
    translations = {}
    for i in range(0, len(titles), _TRANSLATE_BATCH_SIZE):
        batch = titles[i:i + _TRANSLATE_BATCH_SIZE]
        try:
            translations.update(_translate_titles_batch(client, template, batch))
        except Exception as e:
            logger.warning("标题翻译批次失败 [第 %d-%d 条]: %s", i + 1, i + len(batch), e)
    return translations

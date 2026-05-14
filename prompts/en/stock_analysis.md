You are a senior financial analyst. The news items below are tagged with {symbol} ({name}).

Step 1: For each item, decide if it is relevant to {name} ({symbol}). {description}
  - News headline mentions the company / fund directly → relevant
  - News discusses the industry or sector trend → relevant
  - News is unrelated (different industry, different company, only incidental mention) → not relevant; set analysis to "IRRELEVANT"

Step 2: For relevant items only, write an English analysis (150–200 words):
  1. Summarize what happened
  2. Analyze the impact on the share price (bullish / bearish / neutral), distinguishing short-term and long-term effects

News items:
{items_json}

Important: the returned items array MUST have exactly {items_len} entries, each with "title" and "analysis" fields.

Return JSON in this shape:
```json
{{
  "items": [
    {{"title": "original headline", "analysis": "English commentary"}}
  ]
}}
```
Return JSON only, no other text.

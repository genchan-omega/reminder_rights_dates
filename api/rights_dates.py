# api/cross_calendar.py
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI()

CALENDAR_URL = "https://gokigen-life.tokyo/calendar/"

DATE_RE = re.compile(r"^(\d{1,2}月\d{1,2}日\(.+?\))(.*)$")  # 例: 2月18日(水)Today...


def _fetch_html(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; reminder-bot/1.0; +https://example.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    r = requests.get(url, headers=headers, timeout=20)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"fetch failed: {r.status_code}")
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def _extract_weekly_section_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # 見出し「週間優待クロスイベントカレンダー」を探し、その次の見出しまでを対象にする
    start_h2 = None
    for h2 in soup.find_all(["h2", "h3"]):
        t = h2.get_text(strip=True)
        if "週間優待クロスイベントカレンダー" in t:
            start_h2 = h2
            break

    if not start_h2:
        return ""

    chunks: List[str] = []
    for node in start_h2.next_siblings:
        # 次の見出しに到達したら終了（直近優待月イベントカレンダー）
        if getattr(node, "name", None) in ["h2", "h3"]:
            heading = node.get_text(strip=True)
            if "直近優待月イベントカレンダー" in heading:
                break

        # 文字列ノードは無視しがちなので、タグだけ拾う
        if getattr(node, "get_text", None):
            text = node.get_text("\n", strip=True)
            if text:
                chunks.append(text)

    # まとめて整形
    raw = "\n".join(chunks)
    lines = [ln.strip() for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def _parse_rows(section_text: str) -> List[Dict[str, Any]]:
    if not section_text:
        return []

    lines = [ln.strip() for ln in section_text.splitlines() if ln.strip()]

    # 「DATE EVENT」行の後から読む（無ければ全体を読む）
    start_idx = 0
    for i, ln in enumerate(lines):
        if ln.upper().replace(" ", "") == "DATEEVENT":
            start_idx = i + 1
            break
        if ln.upper() == "DATE EVENT":
            start_idx = i + 1
            break

    rows: List[Dict[str, Any]] = []
    cur_date: str | None = None
    cur_events: List[str] = []

    def flush():
        nonlocal cur_date, cur_events
        if cur_date is None:
            return
        if not cur_events:
            cur_events = ["イベントはありません"]
        rows.append({"date": cur_date, "events": cur_events})
        cur_date, cur_events = None, []

    for ln in lines[start_idx:]:
        m = DATE_RE.match(ln)
        if m:
            # 新しい日付
            flush()
            cur_date = m.group(1).strip()
            rest = (m.group(2) or "").strip()
            if rest:
                cur_events.append(rest)
            continue

        if cur_date is None:
            # 日付が始まる前のゴミは捨てる
            continue

        cur_events.append(ln)

    flush()

    # 念のため「イベントはありません」統一
    for r in rows:
        evs = [e for e in r["events"] if e]
        r["events"] = evs if evs else ["イベントはありません"]

    return rows


@app.get("/api/cross_calendar")
def cross_calendar():
    try:
        html = _fetch_html(CALENDAR_URL)
        section = _extract_weekly_section_text(html)
        rows = _parse_rows(section)
        payload = {
            "source": CALENDAR_URL,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "rows": rows,
        }
        return JSONResponse(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"parse error: {e}")

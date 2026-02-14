import re
import json
from http.server import BaseHTTPRequestHandler

import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (compatible; invest-jp-scraper/1.0)"


def fetch_yuutai_days(url: str = "https://www.invest-jp.net/yuutai") -> dict:
    r = requests.get(
        url,
        headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"},
        timeout=15,
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    # ページ全体をテキスト化（改行/空白は後で吸収）
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    # 例:
    # 「次回の権利付最終売買日は2026年2月18日(水)。権利日は2月20日。…」
    pat_last = re.compile(
        r"権利付最終売買日(?:は|：)\s*"
        r"(?P<date>(?:\d{4}年)?\d{1,2}月\d{1,2}日(?:\([^)]+\))?)"
    )
    pat_rights = re.compile(
        r"権利日(?:は|：)\s*"
        r"(?P<date>(?:\d{4}年)?\d{1,2}月\d{1,2}日(?:\([^)]+\))?)"
    )

    m_last = pat_last.search(text)
    m_rights = pat_rights.search(text)

    if not m_last or not m_rights:
        raise RuntimeError("ページから日付を抽出できませんでした（HTML構造/文言が変わった可能性）")

    return {
        "url": url,
        "last_trading_day": m_last.group("date"),  # 例: "2026年2月18日(水)"
        "rights_day": m_rights.group("date"),      # 例: "2月20日"
    }


# ---- Vercel で /api/rights_dates として公開する入口 ----
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            data = fetch_yuutai_days()

            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            # GASから定期的に叩くなら、軽くキャッシュさせると安定します
            self.send_header("Cache-Control", "public, s-maxage=1800, stale-while-revalidate=86400")
            self.end_headers()
            self.wfile.write(body)

        except Exception as e:
            body = json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

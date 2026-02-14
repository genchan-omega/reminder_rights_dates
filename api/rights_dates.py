import re
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

if __name__ == "__main__":
    print(fetch_yuutai_days())

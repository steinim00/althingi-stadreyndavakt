"""Staðreyndapróf á fullyrðingum með Claude og vefleit.

Sami mælikvarði fyrir alla flokka. Niðurstaða er „wrong“ aðeins ef nafngreind
opinber heimild stangast beint á við fullyrðinguna.
"""
import json
import os
import re

import anthropic

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
BATCH = 6

SYSTEM = """Þú ert hlutlaus staðreyndaprófari fyrir ræður á Alþingi. Þú færð fullyrðingar
með nafni ræðumanns (fornafn fyrst), flokki og dagsetningu. Notaðu vefleit og helst
opinberar heimildir (Hagstofa, ráðuneyti, Seðlabanki, Alþingi, stofnanir).

Sami mælikvarði gildir fyrir alla flokka, stjórn og stjórnarandstöðu.
Flokkaðu hverja fullyrðingu:
- "wrong": nafngreind opinber heimild stangast beint á við nákvæma fullyrðingu.
- "open": ekki tókst að staðfesta eða afsanna, eða tölur eru á reiki eða ósambærilegar.
- "ok": staðfest með heimild.
- "skip": skoðun, spá, óljóst orðalag eða ekki hægt að prófa. Slepptu þeim alveg.
Dæmdu aldrei rökstuðning, túlkun eða pólitískt mat. „Fann ekki heimild“ er "open", ekki "wrong".
Ræðumaður getur vísað í tölur sem aðrir nefndu; metið þá tölu sem slíka.

Svaraðu AÐEINS með JSON-lista, enginn annar texti:
[{"i": <númer fullyrðingar>, "status": "wrong|open|ok",
  "title": "stuttur titill á íslensku",
  "facts": "Gögn: 1-3 setningar á íslensku með tölum og heimild",
  "sources": [{"title": "...", "url": "https://..."}]}]"""


def _extract_json(text: str) -> list[dict]:
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict)]


def check_batch(client: anthropic.Anthropic, claims: list[dict]) -> list[dict]:
    lines = []
    for i, c in enumerate(claims):
        lines.append(f'{i}. [{c["party_name"]}] {c["speaker"]} ({c["date"]}): "{c["claim"]}"')
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
        messages=[{"role": "user", "content": "\n".join(lines)}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    results = []
    for d in _extract_json(text):
        try:
            idx = int(d["i"])
            base = claims[idx]
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        if d.get("status") not in ("wrong", "open", "ok"):
            continue
        results.append(
            {
                "status": d["status"],
                "title": str(d.get("title", ""))[:140],
                "claim": base["claim"],
                "speaker": base["speaker"],
                "party": base["party_name"],
                "date": base["date"],
                "facts": str(d.get("facts", ""))[:900],
                "sources": [
                    {"title": s.get("title", s.get("url", "")), "url": s["url"]}
                    for s in d.get("sources", [])
                    if isinstance(s, dict) and str(s.get("url", "")).startswith("http")
                ][:4],
            }
        )
    return results


def check_all(claims: list[dict], max_claims: int) -> tuple[list[dict], bool]:
    """Skilar (niðurstöðum, lokið). lokið=False ef lykil vantar eða API brást."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY vantar, sleppi staðreyndaprófi.")
        return [], False
    client = anthropic.Anthropic()
    claims = claims[:max_claims]
    out = []
    for i in range(0, len(claims), BATCH):
        try:
            out += check_batch(client, claims[i : i + BATCH])
        except anthropic.APIError as e:
            print(f"API-villa, hætti: {e}")
            return out, False
    return out, True

"""Sækir dagskrá næsta (eða yfirstandandi) þingfundar úr opnum gögnum Alþingis.

Slóðin án færibreytna skilar dagskrá næsta þingfundar, eða fundarins sem er í gangi.
Ef vefurinn lokar á okkur er gamla dagskráin látin standa (sama regla og í fetch.py).
"""
import re
import xml.etree.ElementTree as ET

import requests

from .fetch import BASE, _get, _local

URL = f"{BASE}/altext/xml/dagskra/thingfundur/"


def _text(el: ET.Element, name: str) -> str:
    for ch in el:
        if _local(ch.tag) == name:
            return re.sub(r"\s+", " ", "".join(ch.itertext())).strip()
    return ""


def _item_url(lthing: str, nr: str, flokkur: str) -> str:
    # Slóðirnar í XML-inu eru bilaðar ("http://http://"), svo þær eru smíðaðar upp á nýtt.
    if not nr:
        return ""
    kind = "bferill" if flokkur == "B" else "ferill"
    return f"{BASE}/thingstorf/thingmalalistar-eftir-thingum/{kind}/?ltg={lthing}&mnr={nr}"


def parse(xml: str) -> dict | None:
    root = ET.fromstring(xml.encode("utf-8"))
    fundur = next((e for e in root.iter() if _local(e.tag) == "þingfundur"), None)
    if fundur is None:
        return None
    hefst = next((c for c in fundur if _local(c.tag) == "hefst"), None)
    lthing = fundur.get("þingnúmer", "")
    items = []
    dagskra = next((c for c in fundur if _local(c.tag) == "dagskrá"), None)
    for li in (dagskra if dagskra is not None else []):
        if _local(li.tag) != "dagskrárliður":
            continue
        mal = next((c for c in li if _local(c.tag) == "mál"), None)
        if mal is None:
            continue
        who = _text(mal, "málshefjandi") or _text(mal, "fyrirspyrjandi")
        to = _text(mal, "til_andsvara") or _text(mal, "til_svara")
        items.append({
            "nr": li.get("númer", ""),
            "title": _text(mal, "málsheiti"),
            "topic": _text(mal, "efnisgreining"),
            "kind": _text(mal, "málstegund"),
            "stage": _text(li, "umræða"),
            "who": who,
            "to": to,
            "url": _item_url(lthing, mal.get("málsnúmer", ""), mal.get("málsflokkur", "")),
        })
    return {
        "lthing": lthing,
        "fundur": fundur.get("númer", ""),
        "name": _text(fundur, "fundarheiti"),
        # <texti> í XML-inu er rangur ("1:30 árdegis"), svo notað er <dagur> og <timi>
        "date": _text(hefst, "dagur") if hefst is not None else "",
        "time": _text(hefst, "timi") if hefst is not None else "",
        "started": bool(_text(fundur, "fundursettur")),
        "ended": bool(_text(fundur, "fuslit")),
        "items": items,
    }


def fetch_agenda(session: requests.Session) -> dict | None:
    return parse(_get(session, URL))

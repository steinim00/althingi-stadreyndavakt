"""Sækir ræðulista og ræður frá althingi.is.

Reglur:
- Aðeins nýjar ræður (ekki í data/seen.json) eru sóttar, með hægum hraða.
- Ef vefurinn svarar með Cloudflare-áskorun eða villu er hætt strax og
  skráð að dagurinn sé ófullkominn. Ekki er reynt að komast framhjá vörninni.
"""
import re
import time
import xml.etree.ElementTree as ET

import requests

BASE = "https://www.althingi.is"
UA = "althingi-stadreyndavakt/1.0 (+https://github.com/steinim00/althingi-stadreyndavakt)"
CF_RE = re.compile(r"_cf_chl_opt|Enable JavaScript and cookies|Just a moment")


class Blocked(Exception):
    pass


def _get(session: requests.Session, url: str) -> str:
    r = session.get(url, timeout=30)
    if r.status_code in (403, 429, 503) or CF_RE.search(r.text[:5000]):
        raise Blocked(f"{url} -> {r.status_code}")
    r.raise_for_status()
    # Vefurinn gefur stundum ISO-8859-1 sem er skráð sem UTF-8
    if "Ã" in r.text or "Â" in r.text:
        try:
            return r.text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return r.text


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def speech_list(session: requests.Session, lthing: int, days: int = 100) -> list[dict]:
    """Ræðulisti síðustu `days` daga (hámark 100 hjá Alþingi)."""
    xml = _get(session, f"{BASE}/altext/xml/raedulisti/?dagar={min(days, 100)}")
    root = ET.fromstring(xml.encode("utf-8"))
    out = []
    for el in root.iter():
        if _local(el.tag) != "ræða":
            continue
        rec = {"nafn": "", "id": "", "dagur": "", "teg": "", "mflokkur": "", "mheiti": "",
               "html": "", "xml": ""}
        for ch in el.iter():
            t = _local(ch.tag)
            txt = (ch.text or "").strip()
            if t == "ræðumaður":
                rec["id"] = ch.get("id", "")
            elif t == "xml" and "/raedur/" in txt:
                rec["xml"] = txt.replace("http://", "https://")
            elif t == "nafn" and not rec["nafn"]:
                rec["nafn"] = txt
            elif t == "dagur":
                rec["dagur"] = txt
            elif t == "tegundræðu":
                rec["teg"] = txt
            elif t == "málsflokkur":
                rec["mflokkur"] = txt
            elif t == "málsheiti":
                rec["mheiti"] = txt
            elif t == "html":
                rec["html"] = txt.replace("http://", "https://")
        if rec["xml"] or rec["html"]:
            if not rec["xml"]:  # smíða XML-slóð úr HTML-slóð
                rec["xml"] = rec["html"].replace("/altext/raeda/", "/xml/").replace(
                    "/xml/158/", "/xml/158/raedur/").replace(".html", ".xml")
            out.append(rec)
    return out


def speech_text(session: requests.Session, xml_url: str) -> str:
    """Texti ræðunnar úr XML-skrá ræðunnar (málsgreinar í <ræðutexti>)."""
    xml = _get(session, xml_url)
    root = ET.fromstring(xml.encode("utf-8"))
    paras = []
    for el in root.iter():
        if _local(el.tag) == "mgr":
            paras.append(re.sub(r"\s+", " ", "".join(el.itertext())).strip())
    return " ".join(p for p in paras if p)


def party_of_mp(session: requests.Session, mp_id: str, lthing: int) -> str:
    """Þingflokkur þingmanns á þinginu (síðasta þingseta), eða "" ef ekki finnst."""
    xml = _get(session, f"{BASE}/altext/xml/thingmenn/thingmadur/thingseta/?nr={mp_id}")
    root = ET.fromstring(xml.encode("utf-8"))
    party = ""
    for seta in root.iter():
        if _local(seta.tag) != "þingseta":
            continue
        thing = next((c.text for c in seta if _local(c.tag) == "þing"), None)
        if (thing or "").strip() != str(lthing):
            continue
        for c in seta:
            if _local(c.tag) == "þingflokkur" and (c.text or "").strip():
                party = c.text.strip()
    return party


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def polite_sleep(seconds: float = 1.5) -> None:
    time.sleep(seconds)

"""Fer yfir öll ræðuskjöl heils þings og dregur út fullyrðingar (endurræsanlegt).

Notkun: python -m src.sweep ÚTSKRÁ.jsonl [LTHING]
Hver lína í útskránni er annaðhvort {"done": <xml-slóð>} eða fullyrðing. Ef vefurinn lokar á sóknina
er hætt og hægt að keyra aftur síðar; það sem er búið er ekki sótt aftur. Ekki er reynt að komast
framhjá vörn vefsins.
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from . import extract, fetch
from .run import MIN_SPEECH_CHARS, _html_url, claim_key

TYPES = {"ræða", "flutningsræða", "svar"}  # andsvör o.fl. eru stutt og sleppt
# FOCUS_RE=<regex> takmarkar yfirferðina við mál þar sem heitið passar (t.d. störf þingsins og
# óundirbúnar fyrirspurnir) og sleppir þá reglunni um að sleppa fyrirspurnum.
FOCUS = re.compile(os.environ["FOCUS_RE"], re.IGNORECASE) if os.environ.get("FOCUS_RE") else None


def all_speeches(session, lthing: int) -> list[dict]:
    root = ET.fromstring(fetch._get(session, f"{fetch.BASE}/altext/xml/raedulisti/?lthing={lthing}").encode("utf-8"))
    out = []
    for el in root.iter():
        if fetch._local(el.tag) != "ræða":
            continue
        rec = {"nafn": "", "id": "", "dagur": "", "teg": "", "mheiti": "", "html": "", "xml": ""}
        for ch in el.iter():
            t, txt = fetch._local(ch.tag), (ch.text or "").strip()
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
            elif t == "málsheiti":
                rec["mheiti"] = txt
            elif t == "html":
                rec["html"] = txt.replace("http://", "https://")
        if not rec["xml"] or rec["teg"] not in TYPES:
            continue
        if FOCUS is not None:
            if FOCUS.search(rec["mheiti"]):
                out.append(rec)
        elif not extract.is_skippable(rec["mheiti"], rec["teg"]):
            out.append(rec)
    return out


def main(out_path: str, lthing: int = 158) -> None:
    out = Path(out_path)
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                if "done" in d:
                    done.add(d["done"])
    root = Path(__file__).resolve().parent.parent
    parties = json.loads((root / "data" / "parties.json").read_text(encoding="utf-8")) if (root / "data" / "parties.json").exists() else {}
    session = fetch.make_session()
    speeches = [s for s in all_speeches(session, lthing) if s["xml"] not in done]
    print(f"{len(speeches)} ræður eftir", flush=True)
    with out.open("a", encoding="utf-8") as f:
        for n, s in enumerate(speeches, 1):
            try:
                fetch.polite_sleep()
                if s["id"] and s["id"] not in parties:
                    parties[s["id"]] = extract.canon_party(fetch.party_of_mp(session, s["id"], lthing))
                    fetch.polite_sleep()
                text = fetch.speech_text(session, s["xml"])
            except fetch.Blocked as e:
                print(f"Lokað: {e}. Hætti.", flush=True)
                break
            except Exception as e:
                print(f"Sleppi {s['xml']}: {e}", flush=True)
                continue
            party = parties.get(s["id"], "")
            if party and len(text) >= MIN_SPEECH_CHARS:
                for c in extract.claim_sentences(text):
                    f.write(json.dumps({"key": claim_key(s["nafn"], s["dagur"], c), "speaker": s["nafn"], "party": party,
                                        "date": s["dagur"], "claim": c, "speech": _html_url(s), "topic": s["mheiti"]},
                                       ensure_ascii=False) + "\n")
            f.write(json.dumps({"done": s["xml"]}) + "\n")
            f.flush()
            if n % 50 == 0:
                print(f"{n}/{len(speeches)}", flush=True)
    (root / "data" / "parties.json").write_text(json.dumps(parties, ensure_ascii=False, indent=1), encoding="utf-8")
    print("búið", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 158)

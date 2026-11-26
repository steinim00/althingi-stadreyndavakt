"""Sækir fullar ræður tiltekinna flokka í data/dump/ (til handvirkrar yfirlestrar).
Notkun: DUMP_PARTIES="Samfylkingin,Viðreisn,Flokkur fólksins" python -m src.dump
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

from . import extract, fetch

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "dump"
LTHING = int(os.environ.get("LTHING", "158"))
START = datetime.strptime(os.environ.get("DUMP_START", "2026-11-19"), "%Y-%m-%d")
WANT = {p.strip() for p in os.environ.get("DUMP_PARTIES", "Samfylkingin,Viðreisn,Flokkur fólksins").split(",")}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pj = ROOT / "data" / "parties.json"
    parties = json.loads(pj.read_text(encoding="utf-8")) if pj.exists() else {}
    s = fetch.make_session()
    days = (datetime.utcnow() - START).days + 2
    n = 0
    for sp in fetch.speech_list(s, LTHING, days):
        try:
            d = datetime.strptime(sp["dagur"], "%d.%m.%Y")
        except ValueError:
            continue
        if d < START or extract.is_skippable(sp["mheiti"], sp["teg"]):
            continue
        try:
            if sp["id"] not in parties:
                fetch.polite_sleep()
                parties[sp["id"]] = extract.canon_party(fetch.party_of_mp(s, sp["id"], LTHING))
            if parties[sp["id"]] not in WANT:
                continue
            fetch.polite_sleep()
            text = fetch.speech_text(s, sp["xml"])
        except fetch.Blocked as e:
            print(f"Lokað: {e}")
            break
        if len(text) < 300:
            continue
        slug = re.sub(r"\W+", "_", f'{d:%Y%m%d}_{sp["nafn"]}')[:60]
        url = sp["html"] or sp["xml"]
        (OUT / f"{slug}_{sp['xml'][-11:-4]}.txt").write_text(
            f'{sp["nafn"]} ({parties[sp["id"]]}) {sp["dagur"]}\n{url}\nMál: {sp["mheiti"]}\n\n{text}\n', encoding="utf-8")
        n += 1
    print(f"Vistaði {n} ræður")


if __name__ == "__main__":
    main()

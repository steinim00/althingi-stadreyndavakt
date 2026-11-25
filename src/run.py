"""Daglegt keyrsluskref: sækja nýjar ræður, prófa fullyrðingar, endurgera síðuna.

Án ANTHROPIC_API_KEY er ekkert prófað sjálfkrafa: fullyrðingarnar fara í
data/candidates.json og birtast sem „óyfirfarið“ þar til einhver fer yfir þær.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import check, extract, fetch
from .render import render

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LTHING = int(os.environ.get("LTHING", "158"))
START = datetime.strptime(os.environ.get("START_DATE", "2026-11-19"), "%Y-%m-%d")
MAX_FETCH = int(os.environ.get("MAX_FETCH", "150"))
MAX_CLAIMS = int(os.environ.get("MAX_CLAIMS", "40"))
MAX_CANDIDATES = int(os.environ.get("MAX_CANDIDATES", "300"))
MIN_SPEECH_CHARS = 300  # styttri ræður eru nær alltaf fundarstjórn


def load(name: str, default):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save(name: str, obj) -> None:
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def claim_key(speaker: str, date: str, claim: str) -> str:
    return hashlib.sha1(f"{speaker}|{date}|{claim[:80]}".encode()).hexdigest()[:12]


def _norm(t: str) -> str:
    return "".join(ch for ch in t.lower() if ch.isalnum())


def _same_person(a: str, b: str) -> bool:
    wa, wb = set(a.lower().split()), set(b.lower().split())
    return bool(wa) and bool(wb) and (wa <= wb or wb <= wa)


def _html_url(s: dict) -> str:
    if s.get("html"):
        return s["html"]
    return s["xml"].replace("/xml/", "/altext/raeda/").replace("/raedur/", "/").replace(".xml", ".html")


def backfill(session, items: list, budget: int) -> int:
    """Finnur ræðuna á bak við hverja fullyrðingu sem vantar slóð á ræðu."""
    todo = [i for i in items if not i.get("speech") and i.get("tries", 0) < 3]
    if not todo or budget <= 0:
        return 0
    dates = []
    for i in todo:
        try:
            dates.append(datetime.strptime(i["date"], "%d.%m.%Y"))
        except ValueError:
            pass
    if not dates:
        return 0
    days = (datetime.now(timezone.utc).replace(tzinfo=None) - min(dates)).days + 2
    try:
        allsp = fetch.speech_list(session, LTHING, days)
    except fetch.Blocked as e:
        print(f"Backfill lokað: {e}")
        return 0
    cache: dict = {}
    used = 0
    for i in todo:
        sps = [x for x in allsp if x["dagur"] == i["date"] and _same_person(i["speaker"], x["nafn"])]
        needle = _norm(i["claim"])[:60]
        found = ""
        for x in sps:
            if x["xml"] not in cache:
                if used >= budget:
                    break
                try:
                    fetch.polite_sleep()
                    cache[x["xml"]] = _norm(fetch.speech_text(session, x["xml"]))
                except fetch.Blocked as e:
                    print(f"Backfill lokað: {e}")
                    return used
                except Exception as e:
                    print(f"Backfill sleppir {x['xml']}: {e}")
                    cache[x["xml"]] = ""
                used += 1
            if needle and needle in cache.get(x["xml"], ""):
                found = _html_url(x)
                break
        if found:
            i["speech"] = found
        else:
            i["tries"] = i.get("tries", 0) + 1
            if sps:
                i["speech_guess"] = [_html_url(x) for x in sps][:3]
    return used


def main() -> int:
    seen: dict = load("seen.json", {"urls": []})
    seen_urls = set(seen["urls"])
    findings: list = load("findings.json", [])
    known_keys = {f.get("key") for f in findings}
    candidates: list = load("candidates.json", [])
    cand_keys = {c["key"] for c in candidates}
    parties: dict = load("parties.json", {})  # þingmannsnúmer -> þingflokkur

    session = fetch.make_session()
    blocked = False
    days_back = (datetime.now(timezone.utc).replace(tzinfo=None) - START).days + 2
    try:
        speeches = fetch.speech_list(session, LTHING, days_back)
    except fetch.Blocked as e:
        print(f"Ræðulisti lokaður: {e}")
        speeches, blocked = [], True

    chosen = []
    for s in speeches:
        try:
            d = datetime.strptime(s["dagur"], "%d.%m.%Y")
        except ValueError:
            continue
        if d < START or extract.is_skippable(s["mheiti"], s["teg"]):
            continue
        chosen.append(s)

    todo = [s for s in chosen if s["xml"] not in seen_urls][:MAX_FETCH]
    new_claims, fetched = [], []
    for s in todo:
        try:
            fetch.polite_sleep()
            if s["id"] and s["id"] not in parties:
                parties[s["id"]] = extract.canon_party(fetch.party_of_mp(session, s["id"], LTHING))
                fetch.polite_sleep()
            text = fetch.speech_text(session, s["xml"])
        except fetch.Blocked as e:
            print(f"Lokað: {e}. Hætti, restin bíður næstu keyrslu.")
            blocked = True
            break
        except Exception as e:  # ein ræða sem brotnar á ekki að stöðva keyrsluna
            print(f"Sleppi {s['xml']}: {e}")
            fetched.append(s["xml"])
            continue
        fetched.append(s["xml"])
        party = parties.get(s["id"], "")
        if not party or len(text) < MIN_SPEECH_CHARS:
            continue
        for c in extract.claim_sentences(text):
            key = claim_key(s["nafn"], s["dagur"], c)
            if key in known_keys or key in cand_keys:
                continue
            new_claims.append(
                {"key": key, "speaker": s["nafn"], "party_name": party,
                 "date": s["dagur"], "claim": c, "speech": _html_url(s)}
            )

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    results = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        pool = candidates and [
            {"key": c["key"], "speaker": c["speaker"], "party_name": c["party"],
             "date": c["date"], "claim": c["claim"], "speech": c.get("speech", "")} for c in candidates
        ] or []
        results, complete = check.check_all(pool + new_claims, MAX_CLAIMS)
        speech_by_key = {c["key"]: c.get("speech", "") for c in pool + new_claims}
        by_claim = {(c["speaker"], c["date"], c["claim"]): c["key"] for c in pool + new_claims}
        for r in results:
            key = by_claim.get((r["speaker"], r["date"], r["claim"]))
            if key and key not in known_keys:
                findings.append({**r, "key": key, "checked": stamp,
                                 "speech": speech_by_key.get(key, "")})
                known_keys.add(key)
        if complete:
            seen["urls"] = sorted(seen_urls | set(fetched))
        candidates = [c for c in candidates if c["key"] not in known_keys]
        if not complete:
            candidates += [{"key": c["key"], "speaker": c["speaker"], "party": c["party_name"],
                            "date": c["date"], "claim": c["claim"], "speech": c.get("speech", "")} for c in new_claims
                           if c["key"] not in {x["key"] for x in candidates}]
    else:
        # án API-lykils: engin sjálfvirk staðreyndapróf, fullyrðingar bíða yfirferðar
        seen["urls"] = sorted(seen_urls | set(fetched))
        candidates += [{"key": c["key"], "speaker": c["speaker"], "party": c["party_name"],
                        "date": c["date"], "claim": c["claim"], "speech": c.get("speech", "")} for c in new_claims]
    candidates = candidates[-MAX_CANDIDATES:]

    used = backfill(session, findings + candidates, int(os.environ.get("BACKFILL_FETCH", "80")))
    if used:
        print(f"Backfill: sótti {used} ræður til að finna slóðir")

    save("seen.json", seen)
    save("candidates.json", candidates)
    save("parties.json", parties)
    save("findings.json", findings)

    done = set(seen["urls"])
    per_day: dict = {}
    for s in chosen:
        d = per_day.setdefault(s["dagur"], {"total": 0, "read": 0})
        d["total"] += 1
        if s["xml"] in done:
            d["read"] += 1
    save("coverage.json", {"days": per_day, "blocked": blocked, "updated": stamp,
                           "start": START.strftime("%d.%m.%Y")})

    render(ROOT)
    print(f"Ræður sóttar: {len(fetched)}, nýjar fullyrðingar: {len(new_claims)}, "
          f"niðurstöður: {len(results)}, lokað: {blocked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

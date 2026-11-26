"""Býr til docs/index.html úr data/*.json og src/template.html."""
import html
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

MONTHS = ["janúar", "febrúar", "mars", "apríl", "maí", "júní", "júlí", "ágúst",
          "september", "október", "nóvember", "desember"]

SECTIONS = [
    ("wrong", "Líklega rangt eða ónákvæmt",
     "Þessar fullyrðingar standast ekki þau gögn sem fundust. Það er ekki sama og að þær séu vísvitandi rangar.",
     "Líklega rangt"),
    ("open", "Óstaðfest", "Hvorki fannst stuðningur né andstaða í opinberum gögnum.", "Óstaðfest"),
    ("ok", "Staðfest rétt", "Þessar fullyrðingar stemma við opinberar heimildir.", "Rétt"),
]
E = html.escape


def _parse(d: str) -> datetime:
    try:
        return datetime.strptime(d, "%d.%m.%Y")
    except ValueError:
        return datetime(2000, 1, 1)


def _pretty(d: str) -> str:
    try:
        x = datetime.strptime(d, "%d.%m.%Y")
        return f"{x.day}. {MONTHS[x.month - 1]}"
    except ValueError:
        return d


def _speech_link(url: str, claim: str) -> str:
    """Slóð á ræðuna; nútímavafrar auðkenna upphaf tilvitnunarinnar á síðunni."""
    words = claim.replace("…", " ").split()[:6]
    frag = urllib.parse.quote(" ".join(words), safe="") if len(words) >= 3 else ""
    return url + (f"#:~:text={frag}" if frag else "")


def _speech_block(f: dict, extra_class: str = "") -> str:
    if f.get("speech"):
        href = _speech_link(f["speech"], f["claim"])
        link = f'<a href="{E(href, quote=True)}">Opna ræðuna á althingi.is</a>'
    elif f.get("speech_guess"):
        links = ", ".join(
            f'<a href="{E(u, quote=True)}">ræða {i}</a>' for i, u in enumerate(f["speech_guess"], 1)
        )
        link = f"Ekki tókst að finna nákvæma ræðu. Ræður þingmannsins þann dag: {links}"
    else:
        link = "Slóð á ræðuna fannst ekki."
    return (
        f'  <div class="cite{extra_class}">\n'
        f'    <p class="cite-h">Úr ræðu</p>\n'
        f'    <blockquote>„{E(f["claim"])}“</blockquote>\n'
        f'    <p class="cite-l"><strong>{E(f["speaker"])}</strong>, {E(f["party"])}, {E(_pretty(f["date"]))} · {link}</p>\n'
        f"  </div>"
    )


def card(f: dict) -> str:
    srcs = ""
    if f.get("sources"):
        links = "".join(
            f'<li><a href="{E(s["url"], quote=True)}">{E(s["title"])}</a></li>' for s in f["sources"]
        )
        srcs = f'  <div class="cite src">\n    <p class="cite-h">Heimildir</p>\n    <ul>{links}</ul>\n  </div>'
    pill = {"wrong": "Líklega rangt", "open": "Óstaðfest", "ok": "Rétt"}[f["status"]]
    return (
        f'<article class="card" data-s="{f["status"]}">\n'
        f'  <span class="pill {f["status"]}">{pill}</span>\n'
        f'  <h3>{E(f["title"])}</h3>\n'
        f'{_speech_block(f)}\n'
        f'  <p class="facts"><strong>Niðurstaða:</strong> {E(f["facts"])}</p>\n'
        f"{srcs}\n</article>"
    )


def render(root: Path) -> None:
    data = root / "data"
    findings = json.loads((data / "findings.json").read_text(encoding="utf-8"))
    cov_p = data / "coverage.json"
    cov = json.loads(cov_p.read_text(encoding="utf-8")) if cov_p.exists() else {}
    tpl = (root / "src" / "template.html").read_text(encoding="utf-8")
    cand_p = data / "candidates.json"
    cands = json.loads(cand_p.read_text(encoding="utf-8")) if cand_p.exists() else []

    counts = {k: sum(1 for f in findings if f["status"] == k) for k in ("wrong", "open", "ok")}
    tiles = (
        '<section class="summary" aria-label="Yfirlit">\n'
        f'  <button type="button" class="tile wrong" data-f="wrong"><b>{counts["wrong"]}</b><span>líklega röng eða ónákvæm</span></button>\n'
        f'  <button type="button" class="tile open" data-f="open"><b>{counts["open"]}</b><span>óstaðfest</span></button>\n'
        f'  <button type="button" class="tile ok" data-f="ok"><b>{counts["ok"]}</b><span>staðfest rétt</span></button>\n'
        f'  <button type="button" class="tile new" data-f="new"><b>{len(cands)}</b><span>óyfirfarnar fullyrðingar</span></button>\n'
        "</section>"
    )

    gaps = [
        f"{_pretty(d)}: {v['total'] - v['read']} af {v['total']} ræðum ólesnar"
        for d, v in sorted((cov.get("days") or {}).items(), key=lambda kv: _parse(kv[0]))
        if v["read"] < v["total"]
    ]
    limits = ['<section class="limits" aria-label="Takmarkanir">', "  <strong>Hvað þetta nær yfir</strong>", "  <ul>"]
    limits.append("    <li>Sjálfvirki hlutinn finnur aðeins setningar með tölum. Staðreyndavillur án talna (rangar fullyrðingar um atburði, lög, landafræði eða hvað einhver sagði) finnast ekki sjálfkrafa heldur aðeins þegar ræða er lesin í heild. Túlkun, rökstuðningur og pólitískt mat eru ekki metin. Fyrirspurnir og fundarstjórn eru undanskilin.</li>")
    limits.append("    <li>„Fann ekki heimild“ þýðir ekki að fullyrðingin sé röng.</li>")
    if cov.get("start"):
        limits.append(f"    <li>Sjálfvirk lestur nær yfir ræður frá {_pretty(cov['start'])}. Eldri niðurstöður voru unnar handvirkt og ná ekki yfir allar ræður.</li>")
    if gaps:
        limits.append("    <li>Ólesið enn: " + "; ".join(E(g) for g in gaps) + ". Vörn vefsins getur lokað á sókn og þá er ekki reynt að komast framhjá henni.</li>")
    limits += ["  </ul>", "</section>"]

    cards = []
    for status, title, lede, _ in SECTIONS:
        items = sorted((f for f in findings if f["status"] == status), key=lambda f: _parse(f["date"]), reverse=True)
        if not items:
            continue
        cards.append(f"<h2>{title}</h2>\n<p class=\"lede\">{lede}</p>")
        cards += [card(f) for f in items]

    if cands:
        cards.append("<h2>Óyfirfarið</h2>\n<p class=\"lede\">Tölur og fullyrðingar sem hafa verið dregnar út úr ræðum en ekki sannreyndar enn. Þær eru hvorki staðfestar né hraktar.</p>")
        for c in sorted(cands, key=lambda c: _parse(c["date"]), reverse=True)[:60]:
            cards.append(
                '<article class="card" data-s="new">\n  <span class="pill new">Óyfirfarið</span>\n'
                f'  <p class="who">{E(c["speaker"])}, {E(c["party"])} · {E(_pretty(c["date"]))}</p>\n'
                f'{_speech_block({**c, "speaker": c["speaker"], "party": c["party"]})}\n</article>'
            )

    seen_urls, sources = set(), []
    for f in findings:
        for s in f.get("sources", []):
            if s["url"] not in seen_urls:
                seen_urls.add(s["url"])
                sources.append(f'  <li><a href="{E(s["url"], quote=True)}">{E(s["title"])}</a></li>')

    updated = cov.get("updated") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    u = datetime.strptime(updated, "%Y-%m-%d")
    meta = f'<p class="meta">Síðast keyrt {u.day}. {MONTHS[u.month - 1]} {u.year}.</p>'
    meta = meta.replace('<p class="meta">', "").replace("</p>", "")

    out = (tpl.replace("{{TILES}}", tiles).replace("{{LIMITS}}", "\n".join(limits))
              .replace("{{CARDS}}", "\n\n".join(cards)).replace("{{SOURCES}}", "\n".join(sources))
              .replace("{{META}}", meta))
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "index.html").write_text(out, encoding="utf-8")


if __name__ == "__main__":
    render(Path(__file__).resolve().parent.parent)

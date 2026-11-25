"""Býr til docs/index.html úr data/*.json og src/template.html."""
import html
import json
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


def card(f: dict) -> str:
    srcs = ""
    if f.get("sources"):
        links = ", ".join(
            f'<a href="{E(s["url"], quote=True)}">{E(s["title"])}</a>' for s in f["sources"]
        )
        srcs = f'<p class="facts"><strong>Heimildir:</strong> {links}</p>'
    pill = {"wrong": "Líklega rangt", "open": "Óstaðfest", "ok": "Rétt"}[f["status"]]
    return (
        f'<article class="card" data-s="{f["status"]}">\n'
        f'  <span class="pill {f["status"]}">{pill}</span>\n'
        f'  <h3>{E(f["title"])}</h3>\n'
        f'  <p class="who">{E(f["speaker"])}, {E(f["party"])} · {E(_pretty(f["date"]))}</p>\n'
        f'  <p class="claim">{E(f["claim"])}</p>\n'
        f'  <p class="facts"><strong>Gögn:</strong> {E(f["facts"])}</p>\n'
        f"  {srcs}\n</article>"
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
        f'  <div class="tile wrong"><b>{counts["wrong"]}</b><span>líklega röng eða ónákvæm</span></div>\n'
        f'  <div class="tile open"><b>{counts["open"]}</b><span>óstaðfest</span></div>\n'
        f'  <div class="tile ok"><b>{counts["ok"]}</b><span>staðfest rétt</span></div>\n'
        f'  <div class="tile new"><b>{len(cands)}</b><span>óyfirfarnar fullyrðingar</span></div>\n'
        "</section>"
    )

    gaps = [
        f"{_pretty(d)}: {v['total'] - v['read']} af {v['total']} ræðum ólesnar"
        for d, v in sorted((cov.get("days") or {}).items(), key=lambda kv: _parse(kv[0]))
        if v["read"] < v["total"]
    ]
    limits = ['<section class="limits" aria-label="Takmarkanir">', "  <strong>Hvað þetta nær yfir</strong>", "  <ul>"]
    limits.append("    <li>Leitað er að tölum og fullyrðingum sem hægt er að bera saman við opinber gögn. Túlkun, rökstuðningur og pólitískt mat eru ekki metin. Fyrirspurnir og fundarstjórn eru undanskilin.</li>")
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
                f'  <p class="claim">{E(c["claim"])}</p>\n</article>'
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

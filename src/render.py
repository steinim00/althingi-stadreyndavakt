"""Býr til docs/index.html úr data/*.json og src/template.html."""
import html
import json
import re
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
        f'    <p class="cite-l">Ræða {E(_pretty(f["date"]))} · {link}</p>\n'
        f"  </div>"
    )


def _attrs(f: dict) -> str:
    """data-* fyrir leit og flokkasíu á spjaldi (JS í template.html)."""
    hay = " ".join(str(f.get(k, "")) for k in ("speaker", "party", "title", "claim", "facts")).lower()
    return f'data-party="{E(f["party"], quote=True)}" data-search="{E(hay, quote=True)}"'


WEEKDAYS = ["mánudagur", "þriðjudagur", "miðvikudagur", "fimmtudagur", "föstudagur",
            "laugardagur", "sunnudagur"]


def _agenda(ag: dict | None) -> str:
    """Dagskrá næsta þingfundar. Fyrirsögnin ("í dag" / "næsti") er stillt í vafranum
    út frá data-date, svo hún úreldist ekki milli keyrslna."""
    if not ag or not ag.get("items"):
        return ""
    try:
        d = datetime.strptime(ag["date"], "%d.%m.%Y")
    except ValueError:
        return ""
    when = f"{WEEKDAYS[d.weekday()]} {d.day}. {MONTHS[d.month - 1]} kl. {E(ag.get('time', ''))}"
    lis = []
    for it in ag["items"]:
        title = E(it["title"])
        if it.get("url"):
            title = f'<a href="{E(it["url"], quote=True)}">{title}</a>'
        lis.append(f"<li>{title}</li>")
    iso = d.strftime("%Y-%m-%d")
    return (
        f'<section class="agenda" id="dagskra" data-date="{iso}" aria-labelledby="ag-h">\n'
        '<h2 id="ag-h"><span id="ag-label">Næsti þingfundur</span></h2>\n'
        f'<p class="lede">{E(ag.get("name", ""))} · {when}</p>\n'
        f'<ol class="ag-list">\n{chr(10).join(lis)}\n</ol>\n'
        '<p class="more"><a href="https://www.althingi.is/thingstorf/thingfundir-og-raedur/thingfundir/" rel="noopener">Öll dagskráin →</a></p>\n'
        "</section>"
    )


# Ríkisstjórn frá desember 2024. Uppfæra ef stjórnarsamstarf breytist.
GOVERNMENT = ("Samfylkingin", "Viðreisn", "Flokkur fólksins")
OPPOSITION_FOCUS = "Sjálfstæðisflokkurinn"


ART = (
    '<svg class="art-arches" aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">'
    '<defs><pattern id="arch" width="64" height="40" patternUnits="userSpaceOnUse">'
    '<path class="arc-a" d="M0 40A32 32 0 0 1 64 40"/>'
    '<path class="arc-b" d="M-32 40A32 32 0 0 1 32 40M32 40A32 32 0 0 1 96 40"/></pattern></defs>'
    '<rect width="100%" height="100%" fill="url(#arch)"/></svg>'
    '<svg class="art-band" aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">'
    '<defs><pattern id="rib" width="32" height="32" patternUnits="userSpaceOnUse">'
    '<path class="rib-a" d="M-4 -4L36 36M36 -4L-4 36"/><path class="rib-b" d="M-4 -4L36 36M36 -4L-4 36"/></pattern></defs>'
    '<rect width="100%" height="100%" fill="url(#rib)"/></svg>'
)


def _hero_stats(subset: list) -> str:
    n = {k: sum(1 for f in subset if f["status"] == k) for k in ("wrong", "open", "ok")}
    return (
        '<div class="hero-stats">'
        f'<div class="w"><b>{n["wrong"]}</b><span>líklega rangt</span></div>'
        f'<div class="o"><b>{n["open"]}</b><span>óstaðfest</span></div>'
        f'<div class="k"><b>{n["ok"]}</b><span>rétt</span></div></div>'
    )


def _hero_panel(pid: str, label: str, subset: list, active: bool) -> str:
    wrong = sorted((f for f in subset if f["status"] == "wrong"), key=lambda f: _parse(f["date"]), reverse=True)
    if wrong:
        f = wrong[0]
        body = (
            '<article class="hero-item">'
            f'<p class="hero-date">{E(_pretty(f["date"]))} · {E(f["speaker"])} · {E(f["party"])}</p>'
            f'<h3>{E(f["title"])}</h3>'
            f'<p class="more"><a href="nidurstodur.html#{E(_anchor(f), quote=True)}">Lesa meira →</a></p></article>'
        )
    else:
        body = '<p class="hero-none">Engin fullyrðing metin líklega röng.</p>'
    return (
        f'<div class="hero-panel{"" if active else " hidden"}" role="tabpanel" id="hp-{pid}" aria-labelledby="ht-{pid}">'
        f'{body}{_hero_stats(subset)}</div>'
    )


def _hero(findings: list, agenda_html: str) -> str:
    gov = [f for f in findings if f["party"] in GOVERNMENT]
    opp = [f for f in findings if f["party"] == OPPOSITION_FOCUS]
    tabs = (("gov", "Stjórnarflokkar", gov), ("d", OPPOSITION_FOCUS, opp))
    chips = "".join(
        f'<button type="button" role="tab" class="chip" id="ht-{i}" data-tab="{i}" aria-controls="hp-{i}" '
        f'aria-selected="{"true" if n == 0 else "false"}">{E(lbl)}</button>'
        for n, (i, lbl, _) in enumerate(tabs)
    )
    panels = "".join(_hero_panel(i, lbl, sub, n == 0) for n, (i, lbl, sub) in enumerate(tabs))
    return (
        f'<div class="hero-art">{ART}\n<div class="hero">\n'
        '<section class="hero-main" aria-label="Líklega rangar fullyrðingar">\n'
        f'<div class="chips" role="tablist" aria-label="Velja hóp">{chips}</div>\n{panels}\n'
        '<p class="more"><a href="nidurstodur.html#f=wrong">Allt líklega rangt →</a></p>\n'
        '</section>\n'
        f'{agenda_html}\n</div></div>'
    )


def _anchor(f: dict) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "-", str(f.get("key", "")))


def _permalink(f: dict) -> str:
    return f' <a class="permalink" href="#{E(_anchor(f), quote=True)}" aria-label="Tengill á þessa fullyrðingu">#</a>' if f.get("key") else ""


def _checked(f: dict) -> str:
    if not f.get("checked"):
        return ""
    try:
        d = datetime.strptime(f["checked"], "%Y-%m-%d")
        return f" <span class=\"checked\">(Athugað {d.day}. {MONTHS[d.month - 1]}.)</span>"
    except ValueError:
        return ""


def _byparty(findings: list) -> str:
    rows: dict = {}
    for f in findings:
        rows.setdefault(f["party"], {"wrong": 0, "open": 0, "ok": 0})[f["status"]] += 1
    if not rows:
        return ""
    order = sorted(rows.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))
    top = max(sum(v.values()) for _, v in order)
    labels = {"wrong": "rangt", "open": "óstaðfest", "ok": "rétt"}
    out = [
        '<section class="byparty" id="flokkar">',
        '<ul class="legend" aria-hidden="true">'
        '<li><span class="sw seg-wrong"></span>Líklega rangt</li>'
        '<li><span class="sw seg-open"></span>Óstaðfest</li>'
        '<li><span class="sw seg-ok"></span>Rétt</li></ul>',
    ]
    for party, v in order:
        total = sum(v.values())
        segs = "".join(
            f'<i class="seg-{k}" style="flex:{v[k]} 1 0"></i>' for k in ("wrong", "open", "ok") if v[k]
        )
        text = " · ".join(f"<b>{v[k]}</b> {labels[k]}" for k in ("wrong", "open", "ok"))
        href = "nidurstodur.html#p=" + urllib.parse.quote(party)
        out.append(
            '<div class="prow">'
            f'<a class="pbtn" href="{E(href, quote=True)}">{E(party)}</a>'
            f'<div class="pbar" style="width:{total / top * 100:.1f}%" aria-hidden="true">{segs}</div>'
            f'<p class="pcount">{text}</p></div>'
        )
    out.append('<p class="note">Úrtakið er ekki slembiúrtak.</p>')
    out.append("</section>")
    return "\n".join(out)


def _head(status: str, title: str, lede: str = "") -> str:
    return f'<div class="sec-head" data-sec="{status}">\n<h2>{E(title)}</h2>\n</div>'


def card(f: dict) -> str:
    srcs = ""
    if f.get("sources"):
        links = "".join(
            f'<li><a href="{E(s["url"], quote=True)}">{E(s["title"])}</a></li>' for s in f["sources"]
        )
        srcs = f'  <div class="cite src">\n    <p class="cite-h">Heimildir</p>\n    <ul>{links}</ul>\n  </div>'
    pill = {"wrong": "Líklega rangt", "open": "Óstaðfest", "ok": "Rétt"}[f["status"]]
    return (
        f'<article class="card" id="{_anchor(f)}" data-s="{f["status"]}" {_attrs(f)}>\n'
        f'  <span class="pill {f["status"]}">{pill}</span>\n'
        f'  <h3>{E(f["speaker"])}</h3>\n'
        f'  <p class="who">{E(f["party"])} · {E(_pretty(f["date"]))}{_permalink(f)}</p>\n'
        f'  <p class="topic">{E(f["title"])}</p>\n'
        f'{_speech_block(f)}\n'
        f'  <p class="facts"><strong>Niðurstaða:</strong> {E(f["facts"])}{_checked(f)}</p>\n'
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
    _fk = {f["key"] for f in findings}
    cands = [c for c in cands if c["key"] not in _fk]
    ag_p = data / "agenda.json"
    ag = json.loads(ag_p.read_text(encoding="utf-8")) if ag_p.exists() else None

    counts = {k: sum(1 for f in findings if f["status"] == k) for k in ("wrong", "open", "ok")}

    def tile(cls, label, n):
        return (f'  <a class="tile {cls}" href="nidurstodur.html#f={cls}">'
                f'<span class="tile-l">{label}</span><b>{n}</b></a>\n')

    tiles = (
        '<section class="summary" aria-label="Yfirlit">\n'
        + tile("wrong", "Líklega rangt", counts["wrong"])
        + tile("open", "Óstaðfest", counts["open"])
        + tile("ok", "Rétt", counts["ok"])
        + tile("new", "Óyfirfarið", len(cands))
        + "</section>"
    )

    gaps = [
        f"{_pretty(d)}: {v['total'] - v['read']} af {v['total']} ræðum ólesnar"
        for d, v in sorted((cov.get("days") or {}).items(), key=lambda kv: _parse(kv[0]))
        if v["read"] < v["total"]
    ]
    limits = ['<section class="limits" aria-label="Takmarkanir">', "  <h2>Takmarkanir</h2>", "  <ul>"]
    limits.append("    <li>Aðeins setningar með tölum finnast sjálfkrafa. Túlkun og pólitískt mat er ekki metið.</li>")
    limits.append("    <li>„Óstaðfest“ þýðir ekki að fullyrðingin sé röng.</li>")
    if cov.get("start"):
        limits.append(f"    <li>Sjálfvirkur lestur nær yfir ræður frá {_pretty(cov['start'])}. Eldri niðurstöður eru handunnar.</li>")
    if gaps:
        limits.append("    <li>Ólesið enn: " + "; ".join(E(g) for g in gaps) + ".</li>")
    limits += ["  </ul>", "</section>"]

    cards = []
    for status, title, lede, _ in SECTIONS:
        items = sorted((f for f in findings if f["status"] == status), key=lambda f: _parse(f["date"]), reverse=True)
        if not items:
            continue
        cards.append(_head(status, title, lede))
        cards += [card(f) for f in items]

    if cands:
        cards.append(_head("new", "Óyfirfarið", "Tölur og fullyrðingar sem hafa verið dregnar út úr ræðum en ekki sannreyndar enn. Þær eru hvorki staðfestar né hraktar."))
        for c in sorted(cands, key=lambda c: _parse(c["date"]), reverse=True)[:60]:
            cards.append(
                f'<article class="card" id="{_anchor(c)}" data-s="new" {_attrs(c)}>\n  <span class="pill new">Óyfirfarið</span>\n'
                f'  <h3>{E(c["speaker"])}</h3>\n  <p class="who">{E(c["party"])} · {E(_pretty(c["date"]))}</p>\n'
                f'{_speech_block({**c, "speaker": c["speaker"], "party": c["party"]})}\n</article>'
            )

    shown_cands = sorted(cands, key=lambda c: _parse(c["date"]), reverse=True)[:60]
    parties = sorted({x["party"] for x in [*findings, *shown_cands] if x.get("party")})
    party_opts = "".join(f'<option value="{E(p, quote=True)}">{E(p)}</option>' for p in parties)

    seen_urls, sources = set(), []
    for f in findings:
        for s in f.get("sources", []):
            if s["url"] not in seen_urls:
                seen_urls.add(s["url"])
                sources.append(f'  <li><a href="{E(s["url"], quote=True)}">{E(s["title"])}</a></li>')

    updated = cov.get("updated") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    u = datetime.strptime(updated, "%Y-%m-%d")
    checked = sorted(f["checked"] for f in findings if f.get("checked"))
    n_today = sum(1 for c in checked if c == updated)
    if n_today:
        extra = f" {n_today} {'ný niðurstaða' if n_today == 1 else 'nýjar niðurstöður'} í dag."
    elif checked:
        d = datetime.strptime(checked[-1], "%Y-%m-%d")
        extra = f" Síðasta athugun {d.day}. {MONTHS[d.month - 1]}."
    else:
        extra = ""
    meta = f'<p class="meta">Síðast keyrt {u.day}. {MONTHS[u.month - 1]} {u.year}.{extra}</p>'
    meta = meta.replace('<p class="meta">', "").replace("</p>", "")

    filters = (
        '<div class="filters" id="nidurstodur" role="group" aria-label="Sía eftir niðurstöðu">\n'
        '  <button type="button" data-f="all" aria-pressed="true">Allt</button>\n'
        '  <button type="button" data-f="wrong" aria-pressed="false">Líklega rangt</button>\n'
        '  <button type="button" data-f="open" aria-pressed="false">Óstaðfest</button>\n'
        '  <button type="button" data-f="ok" aria-pressed="false">Rétt</button>\n'
        '  <button type="button" data-f="new" aria-pressed="false">Óyfirfarið</button>\n</div>\n'
        '<div class="tools" role="search">\n'
        '  <label class="sr-only" for="q">Leita</label>\n'
        '  <input type="search" id="q" placeholder="Leita…" autocomplete="off">\n'
        '  <label class="sr-only" for="party">Flokkur</label>\n'
        f'  <select id="party"><option value="">Allir flokkar</option>{party_opts}</select>\n</div>\n'
        '<p class="status" id="status" role="status" aria-live="polite"></p>\n'
        '<div class="empty hidden" id="empty">Ekkert passar. <button type="button" id="reset">Hreinsa síur</button></div>'
    )
    method = (
        '<section class="method" id="adferd">\n'
        "<ol>\n"
        "  <li>Nýjar ræður eru sóttar daglega úr opnum gögnum Alþingis.</li>\n"
        "  <li>Setningar með tölum eru dregnar út og bornar saman við opinberar heimildir.</li>\n"
        "  <li>Niðurstöður eru unnar af gervigreind með vefleit. Lestu heimildirnar sjálf/ur.</li>\n"
        "</ol>\n<dl>\n"
        "  <dt>Líklega rangt</dt><dd>Opinber heimild stangast á við fullyrðinguna.</dd>\n"
        "  <dt>Óstaðfest</dt><dd>Engin heimild fannst, hvorki með né á móti.</dd>\n"
        "  <dt>Rétt</dt><dd>Stemmir við opinberar heimildir.</dd>\n"
        "  <dt>Óyfirfarið</dt><dd>Dregið út en ekki sannreynt enn.</dd>\n"
        "</dl>\n</section>"
    )
    pages = {
        "index.html": ("", "Staðreyndavakt Alþingis",
                       f'<h1 class="sr-only">Staðreyndavakt Alþingis</h1>\n{_hero(findings, _agenda(ag))}\n{tiles}\n<p class="meta">{meta}</p>'),
        "nidurstodur.html": ("nidurstodur", "Niðurstöður",
                             '<h1 class="page-h">Niðurstöður</h1>\n' + filters + '\n<div class="results">\n' + "\n\n".join(cards) + "\n</div>"),
        "flokkar.html": ("flokkar", "Flokkar", '<h1 class="page-h">Flokkar</h1>\n' + _byparty(findings)),
        "adferd.html": ("adferd", "Aðferð",
                        '<h1 class="page-h">Aðferð</h1>\n' + method + "\n" + "\n".join(limits)
                        + '\n<h2>Heimildir</h2>\n<ul class="sources">\n' + "\n".join(sources) + "\n</ul>"),
    }
    nav_items = (("index.html#dagskra", "Dagskrá", None), ("nidurstodur.html", "Niðurstöður", "nidurstodur"),
                 ("flokkar.html", "Flokkar", "flokkar"), ("adferd.html", "Aðferð", "adferd"))
    (root / "docs").mkdir(exist_ok=True)
    for fname, (cur, title, main) in pages.items():
        nav = "".join(
            f'<a href="{h}"' + (' aria-current="page"' if key and key == cur else "") + f">{lbl}</a>"
            for h, lbl, key in nav_items
        )
        full_title = title if fname == "index.html" else f"{title} · Staðreyndavakt Alþingis"
        out = tpl.replace("{{MAIN}}", main).replace("{{NAV}}", nav).replace("{{TITLE}}", E(full_title))
        (root / "docs" / fname).write_text(out, encoding="utf-8")


if __name__ == "__main__":
    render(Path(__file__).resolve().parent.parent)

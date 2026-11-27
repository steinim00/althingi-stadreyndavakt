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
# Listabókstafir. Merki flokkanna eru sótt úr docs/logos/x<stafur>.(svg|png|webp);
# vanti skrá birtist hlutlaus bókstafsmerking í staðinn.
LIST_LETTER = {"Viðreisn": "C", "Flokkur fólksins": "F", "Samfylkingin": "S", "Sjálfstæðisflokkurinn": "D"}
GOV_ORDER = ("Viðreisn", "Flokkur fólksins", "Samfylkingin")


# Mynstrið (ART) er nú í template.html og nær yfir alla síðuna.


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
            + ('<span class="pill wrong">Staðfest rangt</span>' if f.get("confirmed") else "") +
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


def _logo(root: Path, party: str) -> str:
    letter = LIST_LETTER[party]
    for ext in ("svg", "png", "webp", "jpg"):
        if (root / "docs" / "logos" / f"x{letter}.{ext}").exists():
            return f'<img class="plogo" src="logos/x{letter}.{ext}" alt="{E(party)}" title="{E(party)}">'
    return f'<span class="pbadge" role="img" aria-label="{E(party)}" title="{E(party)}">x{letter}</span>'


def _hero(findings: list, agenda_html: str, root: Path) -> str:
    gov = [f for f in findings if f["party"] in GOVERNMENT]
    opp = [f for f in findings if f["party"] == OPPOSITION_FOCUS]
    tabs = (("gov", "Stjórnarflokkar", gov), ("d", OPPOSITION_FOCUS, opp))
    marks = {"gov": "".join(_logo(root, p) for p in GOV_ORDER), "d": _logo(root, OPPOSITION_FOCUS)}
    names = {"gov": "Stjórnarflokkar: " + ", ".join(GOV_ORDER), "d": OPPOSITION_FOCUS}
    chips = "".join(
        f'<button type="button" role="tab" class="chip chip-logo" id="ht-{i}" data-tab="{i}" aria-controls="hp-{i}" '
        f'aria-label="{E(names[i], quote=True)}" aria-selected="{"true" if n == 0 else "false"}">{marks[i]}</button>'
        for n, (i, lbl, _) in enumerate(tabs)
    )
    panels = "".join(_hero_panel(i, lbl, sub, n == 0) for n, (i, lbl, sub) in enumerate(tabs))
    return (
        '<div class="hero">\n'
        '<section class="hero-main" aria-label="Líklega rangar fullyrðingar">\n'
        f'<div class="chips" role="tablist" aria-label="Velja hóp">{chips}</div>\n{panels}\n'
        '<p class="more"><a href="nidurstodur.html#f=wrong">Allt líklega rangt →</a></p>\n'
        '</section>\n'
        f'{agenda_html}\n</div>'
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
    if f.get("confirmed"):  # staðfest handvirkt af umsjónarmanni síðunnar
        pill = "Staðfest rangt"
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
    wrong = sorted((f for f in findings if f["status"] == "wrong"), key=lambda f: _parse(f["date"]), reverse=True)
    wrong_block = (_head("wrong", "Líklega rangt") + '\n<div class="results">\n' + "\n\n".join(card(f) for f in wrong) + "\n</div>") if wrong else ""
    pages = {
        "index.html": ("", "Staðreyndavakt Alþingis",
                       f'<h1 class="sr-only">Staðreyndavakt Alþingis</h1>\n{_hero(findings, _agenda(ag), root)}\n{tiles}\n{wrong_block}\n<p class="meta">{meta}</p>'),
        "nidurstodur.html": ("nidurstodur", "Niðurstöður",
                             '<h1 class="page-h">Niðurstöður</h1>\n' + filters + '\n<div class="results">\n' + "\n\n".join(cards) + "\n</div>"),
    }
    nav_items = (("index.html#dagskra", "Dagskrá", None), ("nidurstodur.html", "Niðurstöður", "nidurstodur"))
    (root / "docs").mkdir(exist_ok=True)
    for old in ("flokkar.html", "adferd.html"):  # síður sem hafa verið fjarlægðar
        (root / "docs" / old).unlink(missing_ok=True)
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

"""Tekur ræðutexta og dregur út setningar sem hægt er að staðreyndaprófa."""
import re

PARTY_RE = re.compile(r"^(.{0,120}?)\((Sf|V|M|S|F|Flf|P|C)\)[^:]*:")
KEYWORD_RE = re.compile(
    r"(prósent|%|milljarð|milljón|þúsund|krón|tonn|fjölgað|fækkað|hækkað|lækkað|"
    r"hlutfall|árið \d{4}|aukist|minnkað)",
    re.IGNORECASE,
)
SKIP_TOPICS = re.compile(
    r"óundirbúinn fyrirspurnatími|fundarstjórn|dagskrá þingfundar|fyrirspurn",
    re.IGNORECASE,
)

PARTIES = {
    "Sf": "Samfylkingin",
    "V": "Viðreisn",
    "M": "Miðflokkurinn",
    "S": "Sjálfstæðisflokkurinn",
    "F": "Framsókn",
    "Flf": "Flokkur fólksins",
}


def canon_party(name: str) -> str:
    """Samræmir nafn þingflokks úr þingmannaskránni."""
    n = (name or "").lower()
    for key, out in (("samfylking", "Samfylkingin"), ("viðreisn", "Viðreisn"),
                     ("miðflokk", "Miðflokkurinn"), ("sjálfstæð", "Sjálfstæðisflokkurinn"),
                     ("framsókn", "Framsókn"), ("flokkur fólksins", "Flokkur fólksins"),
                     ("píratar", "Píratar"), ("vinstri", "Vinstri græn")):
        if key in n:
            return out
    return name.strip()


def clean_speech(page_text: str) -> str:
    """Klippir ræðutextann út úr texta síðunnar (á milli „Horfa“ og „Næsta ræða“)."""
    txt = re.sub(r"\s+", " ", page_text)
    a = txt.find("Horfa")
    b = txt.find("Næsta ræða")
    if a >= 0:
        txt = txt[a + 5 : b if b > a else None]
    return txt.strip()


def party_of(speech: str) -> str:
    m = PARTY_RE.match(speech)
    return m.group(2) if m else "?"


def strip_header(speech: str) -> str:
    """Fjarlægir ræðumannslínuna („Nafn (S): …“) fremst í textanum."""
    m = PARTY_RE.match(speech)
    return speech[m.end():].strip() if m else speech


def claim_sentences(speech: str, limit: int = 4) -> list[str]:
    """Setningar með tölu og lykilorði, hóflega langar."""
    sents = re.split(r"(?<=[.!?])\s+", speech)
    out = []
    for s in sents:
        if not re.search(r"\d", s):
            continue
        if not KEYWORD_RE.search(s):
            continue
        if not 50 < len(s) < 400:
            continue
        out.append(s.strip())
    # fleiri tölur = líklegra að hægt sé að sannreyna
    out.sort(key=lambda s: -len(re.findall(r"\d[\d.,]*", s)))
    return out[:limit]


def is_skippable(topic: str, kind: str = "") -> bool:
    return bool(SKIP_TOPICS.search(topic or "") or SKIP_TOPICS.search(kind or ""))

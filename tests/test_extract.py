import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from src import extract

SPEECH = ("Horfa Þorgerður Katrín Gunnarsdóttir (V): Við erum ekki bara að stefna í hallalaus fjárlög, "
          "við erum að sjá það að skatttekjur eru núna að fara undir 24% af landsframleiðslu á næsta ári. "
          "Þetta er skoðun mín. Næsta ræða")

def test_party_and_claims():
    txt = extract.clean_speech(SPEECH)
    assert extract.party_of(txt) == "V"
    cl = extract.claim_sentences(extract.strip_header(txt))
    assert len(cl) == 1 and "24%" in cl[0] and "(V)" not in cl[0]

def test_skip():
    assert extract.is_skippable("Óundirbúinn fyrirspurnatími")
    assert not extract.is_skippable("Fjárlög 2027")

if __name__ == "__main__":
    test_party_and_claims(); test_skip(); print("ok")

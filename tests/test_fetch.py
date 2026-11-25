import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from src import fetch

XML = """<?xml version="1.0" encoding="UTF-8"?>
<ns:ræða xmlns:ns="http://skema.althingi.is/skema" skst="ÞKG">
  <ns:umsýsla fundur="34" lgþ="158"><ns:mál nr="206"><ns:málsheiti>ný spá</ns:málsheiti></ns:mál></ns:umsýsla>
  <ns:ræðutexti>
    <ns:mgr>Virðulegi forseti. Vextir eru
    óbreyttir.</ns:mgr>
    <ns:mgr>Verðbólga er 5,9%.</ns:mgr>
  </ns:ræðutexti>
</ns:ræða>"""

class R:
    status_code = 200
    text = XML
    def raise_for_status(self): pass

class S:
    def get(self, url, timeout=30): return R()

def test_speech_text():
    assert fetch.speech_text(S(), "https://x/y.xml") == "Virðulegi forseti. Vextir eru óbreyttir. Verðbólga er 5,9%."

SETA = """<?xml version="1.0" encoding="UTF-8"?>
<þingmaður id='1510'><þingsetur>
<þingseta><þing>156</þing><þingflokkur id='38'>Samfylkingin</þingflokkur></þingseta>
<þingseta><þing>158</þing><þingflokkur id='38'>Samfylkingin</þingflokkur></þingseta>
</þingsetur></þingmaður>"""

def test_party():
    R.text = SETA
    assert fetch.party_of_mp(S(), "1510", 158) == "Samfylkingin"

if __name__ == "__main__":
    test_speech_text(); test_party(); print("ok")

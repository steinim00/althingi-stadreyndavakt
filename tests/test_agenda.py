import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from src import agenda

XML = """<?xml version="1.0" encoding="UTF-8"?><dagskráþingfundar>
<þingfundur númer='44' þingnúmer='158'><fundarheiti>44. fundur</fundarheiti>
<hefst><texti>30. nóvember, kl. 1:30 árdegis</texti><dagur>30.11.2026</dagur><timi>13:30</timi></hefst>
<fundursettur></fundursettur><fuslit></fuslit>
<dagskrá>
<dagskrárliður númer='1'><mál málsnúmer='253' þingnúmer='158' málsflokkur='B'>
<málsheiti>Stafrænt kynferðisofbeldi</málsheiti><málstegund id='um'>sérstök umræða</málstegund>
<málshefjandi id='1414'>Diljá Mist Einarsdóttir</málshefjandi><til_andsvara id='1387'>dómsmálaráðherra</til_andsvara>
<html>http://http://x</html></mál><umræða tegund='*' framhald=''> </umræða></dagskrárliður>
<dagskrárliður númer='2'><mál málsnúmer='134' þingnúmer='158' málsflokkur='A'>
<málsheiti>Evrópska efnahagssvæðið</málsheiti><efnisgreining>bókun 35</efnisgreining>
<málstegund id='l'>Frumvarp til laga</málstegund></mál><umræða tegund='2' framhald=''> 2. umræða</umræða></dagskrárliður>
</dagskrá></þingfundur></dagskráþingfundar>"""

def test_parse():
    ag = agenda.parse(XML)
    assert (ag["fundur"], ag["date"], ag["time"], ag["started"]) == ("44", "30.11.2026", "13:30", False)
    a, b = ag["items"]
    assert a["who"] == "Diljá Mist Einarsdóttir" and a["to"] == "dómsmálaráðherra"
    assert a["url"].endswith("/bferill/?ltg=158&mnr=253") and "http://http" not in a["url"]
    assert b["stage"] == "2. umræða" and b["topic"] == "bókun 35" and "/ferill/?ltg=158&mnr=134" in b["url"]

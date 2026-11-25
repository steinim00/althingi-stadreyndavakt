# Staðreyndavakt Alþingis

Síða sem uppfærist sjálfkrafa á hverjum degi: nýjar ræður þingmanna eru sóttar, tölur og
fullyrðingar bornar saman við opinber gögn og niðurstöðurnar birtar á `docs/index.html`.
Allir flokkar fá sama mælikvarða. „Líklega rangt“ er aðeins sett þegar nafngreind opinber
heimild stangast á við fullyrðinguna; ef heimild finnst ekki er niðurstaðan „óstaðfest“.

## Uppsetning (einu sinni)

1. Settings → Pages → Deploy from a branch → `main` og `/docs`.
   (GitHub Pages á einkasafni krefst greiddrar áskriftar. Annars þarf safnið að vera opinbert.)
2. Actions → „Daglegt staðreyndapróf“ → Run workflow til að prófa strax.
3. Valfrjálst: leyndarmálið `ANTHROPIC_API_KEY` undir Settings → Secrets → Actions kveikir á
   sjálfvirku staðreyndaprófi. Það kostar (API er rukkað sérstaklega). Án lykilsins kostar allt
   ekkert: fullyrðingar eru dregnar út og birtast sem „óyfirfarið“ þar til farið er yfir þær.

## Hvernig þetta virkar

- `src/fetch.py` notar opin XML-gögn Alþingis (`/altext/xml/`): ræðulisti síðustu daga
  (`raedulisti/?dagar=N`), XML-skrá hverrar ræðu og þingseta hvers þingmanns fyrir þingflokk.
  Aðeins nýjar ræður eru sóttar, hægt. Ef vefurinn svarar með Cloudflare-áskorun eða villu er
  hætt, dagurinn skráður sem ófullkominn og reynt aftur næsta dag. Ekki er reynt að komast
  framhjá vörninni.
- `src/extract.py`: dregur út setningar með tölum og fullyrðingum. Fyrirspurnir og fundarstjórn sleppt.
- `src/check.py` (aðeins með API-lykli): Claude með vefleit prófar fullyrðingar (hámark
  `MAX_CLAIMS`, sjálfgefið 40 á dag).
- `src/render.py`: býr til síðuna úr `data/findings.json` og `data/candidates.json`.
- `data/seen.json` heldur utan um lesnar ræður, `data/parties.json` geymir þingflokka.

## Stillingar (umhverfisbreytur)

`START_DATE` (sjálfgefið 2026-11-19), `MAX_FETCH` (150), `MAX_CLAIMS` (40),
`MAX_CANDIDATES` (300), `LTHING` (158), `CLAUDE_MODEL`.

## Þekktar takmarkanir

- Sóknin hefur ekki verið prófuð úr GitHub Actions. Cloudflare gæti lokað á hana. XML-slóðirnar hafa aðeins verið prófaðar úr vafra.
- Niðurstöður eru unnar af gervigreind með vefleit og þarf að lesa með gagnrýni.
- Fyrir 19. nóvember 2026 eru niðurstöður handunnar og ná ekki yfir allar ræður.

Prófun: `python tests/test_extract.py && python tests/test_fetch.py`

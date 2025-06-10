# Wiki2
Wiki2 is een iteratie op de hiervoor bestaande examenwiki. Ze is sneller, simpeler en modern gemaakt.

## Setup
De Python dependencies worden beheerd aan de hand van `uv`. Dat is dus de tool die je allereerst moet [installeren](https://docs.astral.sh/uv/getting-started/installation/). Check dat het juist geïnstalleerd is door gewoon `uv` uit te voeren (je zou een overzicht van de beschikbare commando's moeten krijgen).

### Klaarmaken voor gebruik

Alles begint natuurlijk met het clonen van de repo. Vervolgens kun je je lokale omgeving klaar voor gebruik maken door `uv sync --frozen` uit te voeren (dit maakt ook automatisch een virtual environment aan), of een Django development server uitvoeren met `uv run manage.py runserver` (in het algemeen worden alle `python <programma>.py`-commando's vervangen door `uv run <programma>.py`). 

### Code schrijven in de praktijk

Een extra dependency introduceren doe je met `uv add <naam-van-package>`. Dit wordt dan automatisch geïnstalleerd. Door dit te doen zal ook het bestand `uv.lock` veranderen; dit is volledig normaal. 

## Superuser
usr: `Webteam`
pwd: `Webt3am@Wiki2`
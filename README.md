# Robot Dictionary

Source of [robotdictionary.com](https://robotdictionary.com), a reference of the world's robots revised every day.

## How it is organised

- `data/entries/` holds one small JSON file per robot. Edit a file here to correct an entry; the site rebuilds itself.
- `data/state/` keeps the daily log of changes, the robot of the day history and the review queues.
- `tools/build.py` renders every page, the sitemap, the RSS feed and the open data files from the entries.
- `tools/update.py` runs each morning: it refreshes facts from Wikidata, links sources, adds newly documented robots and checks the Y Combinator directory.
- `.github/workflows/daily.yml` runs the update and build every day at 04:41 UTC. `build.yml` rebuilds after any edit to an entry.

Everything else at the top level is generated. Do not edit generated pages by hand.

## Entry fields

`id`, `name`, `aka`, `section` (humanoids, quadrupeds, wheeled, arms, rovers, medical, marine, other), `kind`, `maker`, `country`, `year`, `status`, `def` (one sentence), `body` (paragraphs), `facts`, `specs` (label and value pairs), `see` (related ids), `refs` (sources with label and url), `ids` (Wikidata and YC identifiers), `added`, `revised`.

Add `"image": "/img/<id>.png"` to an entry and place the picture in `img/` to fill its plate.

## Licence

Entry text and the compiled dataset: CC BY 4.0, credit Robot Dictionary. Quoted Wikipedia text keeps its CC BY-SA 4.0 licence. Wikidata facts are CC0.

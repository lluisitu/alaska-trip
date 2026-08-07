#!/usr/bin/env python3
"""
The paperwork and the empty stretches: pets across the border, cell dead zones,
propane, water and dump on the remote legs.

    cd tools && python3 build_petlog.py

Three things were mentioned in prose across a dozen stops and held nowhere:
what a dog and a cat need to cross into Canada and come back, where the phone
stops working, and where propane and dump stations genuinely run out.

The one that changes the itinerary rather than the packing list is Alaska's
rule: a Certificate of Veterinary Inspection issued within 30 days of entering
the state, for both animals. That certificate cannot be obtained in Austin
before a March departure — it has to come from a vet in Whitehorse, Dawson City
or Fort Nelson within 30 days of the Alaska border. It is a stop on the route,
not a task on a list.

Everything here carries the URL it came from and the date that page was last
modified where the page showed one. Where a fact could not be verified it says
so rather than guessing — the "turn your propane off at the border" advice, for
instance, appears on no government page that could be found, and propane on the
Cassiar could not be confirmed anywhere.

Standard library only; no network.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'
DB = pathlib.Path(__file__).resolve().parent / 'petlog_db.json'


def main():
    h = SRC.read_text()
    db = json.loads(DB.read_text())

    for k in ('pets', 'cell_gaps', 'supplies'):
        if k not in db:
            sys.exit(f"!! petlog_db.json is missing '{k}'")
    for k in ('into_canada', 'back_into_us', 'watch'):
        if k not in db['pets']:
            sys.exit(f"!! petlog_db.json pets section is missing '{k}'")

    # Every requirement and every gap must name its source. An uncited rule is
    # worse than no rule, because it will be believed.
    uncited = []
    for side in ('into_canada', 'back_into_us'):
        for r in db['pets'][side]:
            if not r.get('source'):
                uncited.append(f"pets.{side}: {r.get('requirement','?')[:50]}")
    for g in db['cell_gaps']:
        if not g.get('source'):
            uncited.append(f"cell_gaps: {g.get('road','?')}")
    for s in db['supplies']:
        if not s.get('source'):
            uncited.append(f"supplies: {s.get('topic','?')}")
    if uncited:
        sys.exit("!! uncited entries: " + '; '.join(uncited[:6]))

    payload = json.dumps(db, ensure_ascii=False, sort_keys=True)
    decl = re.compile(r'const PETLOG = \{.*?\};\n', re.S)
    block = f'const PETLOG = {payload};\n'
    if decl.search(h):
        h = decl.sub(lambda _m: block, h, count=1)
    else:
        anchor = 'const PHOTO ='
        assert anchor in h, 'PHOTO declaration missing'
        h = h.replace(anchor, block + '\n' + anchor, 1)
    SRC.write_text(h)

    unver = sum(1 for s in db['supplies'] if 'NOT VERIFIED' in json.dumps(s).upper()) \
          + sum(1 for g in db['cell_gaps'] if 'NOT VERIFIED' in json.dumps(g).upper())
    print(f"  pets: {len(db['pets']['into_canada'])} requirements into Canada, "
          f"{len(db['pets']['back_into_us'])} coming back, {len(db['pets']['watch'])} to re-check")
    print(f"  {len(db['cell_gaps'])} cell-coverage entries · {len(db['supplies'])} supply entries "
          f"({unver} explicitly unverified)")
    print("wrote", SRC)


if __name__ == '__main__':
    main()

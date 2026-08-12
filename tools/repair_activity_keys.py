#!/usr/bin/env python3
"""
Re-attach links_db activity keys that no longer match any headline on the page.

    cd tools && python3 repair_activity_keys.py            # dry run
    cd tools && python3 repair_activity_keys.py --write

Why
---
`build_links` merges an activities entry onto the headline whose text matches it
exactly. A key that matches nothing does nothing, silently — the same failure
that made a shots_db correction a no-op for three commits.

Twenty-nine such keys existed when this was written. The first reading was that
they were lost research. **They were not**, and the distinction matters enough
to record: every headline at every affected stop already carried its links. The
orphans were older wordings left behind when a headline was edited and then
re-researched under its new text. Nothing was missing from the page.

Three causes, none visible by eye:

  * **Apostrophes.** "Creamer's Field" written with a straight quote does not
    match "Creamer’s Field" written with a curly one. Same sentence on screen.
  * **Rewordings.** A headline was edited — "its excellent outdoor museum"
    became "its excellent local museum" — and the db key kept the old text.
  * **Restructures.** Three separate Santa Fe headlines ("Santa Fe Plaza at
    first light.", "Canyon Road galleries.") were later merged into one
    "Day 1-2: …" line. The old keys resemble nothing on the page.

What it will and will not do
----------------------------
Punctuation-only differences are repaired outright: the text is the same.

Rewordings are matched with difflib and only above a high similarity ratio, and
only when the best candidate is clearly better than the runner-up. Anything
below that is REPORTED, never guessed — attaching a researched link to the wrong
headline is worse than leaving it detached, because it looks right.

Run it after any pass that edits headline text.
"""
import difflib, json, pathlib, sys, unicodedata

HERE = pathlib.Path(__file__).resolve().parent
DB = HERE / 'links_db.json'
SRC = HERE.parent / 'desktop' / 'index.html'

RATIO = 0.86          # below this, report rather than guess
MARGIN = 0.04         # best must beat runner-up by this much


def ex(hh, decl, o='[', c=']'):
    i = hh.index(decl); s = hh.index(o, i); d = 0; ins = False; esc = False
    for j in range(s, len(hh)):
        ch = hh[j]
        if ins:
            if esc: esc = False
            elif ch == '\\': esc = True
            elif ch == '"': ins = False
        else:
            if ch == '"': ins = True
            elif ch == o: d += 1
            elif ch == c:
                d -= 1
                if d == 0: return hh[s:j + 1]
    raise ValueError('unterminated: ' + decl)


def flat(s):
    """Same sentence, ignoring the punctuation that renders identically."""
    s = unicodedata.normalize('NFKC', s or '')
    for a, b in (('’', "'"), ('‘', "'"), ('“', '"'), ('”', '"'),
                 ('—', '-'), ('–', '-'), (' ', ' ')):
        s = s.replace(a, b)
    return ' '.join(s.lower().split()).rstrip('.')


def main():
    write = '--write' in sys.argv
    h = SRC.read_text()
    stops = json.loads(ex(h, 'const STOPS =')) + json.loads(ex(h, 'const EXT_DATA =', '{', '}'))['STOPS']
    page = {s['id']: [a['name'] for a in (s.get('activities') or [])] for s in stops}
    db = json.loads(DB.read_text())

    # A stop where every headline already has links cannot be missing anything,
    # so an orphan there is dead weight rather than detached research.
    linked = {x['id']: {a['name'] for a in (x.get('activities') or []) if a.get('links')}
              for x in stops}
    all_linked = {sid: bool(page.get(sid)) and set(page[sid]) == linked.get(sid, set())
                  for sid in page}
    punct = reworded = unmatched = superseded = dead = 0
    for sid, entry in db['stops'].items():
        acts = entry.get('activities') or {}
        names = page.get(sid) or []
        exact = set(names)
        byflat = {}
        for n in names:
            byflat.setdefault(flat(n), n)
        for key in list(acts):
            if key in exact or acts[key].get('add'):
                continue
            hit = byflat.get(flat(key))
            if hit:
                acts[hit] = acts.pop(key)
                punct += 1
                print(f'  punctuation  {sid}: {key[:58]!r}\n            -> {hit[:58]!r}')
                continue
            # Reworded: score against EVERY headline, including ones that
            # already have an entry. Scoring only unclaimed headlines was wrong
            # and made every orphan look like a 0.00 no-match, which hid the
            # real finding: most of these are superseded, not lost.
            scored = sorted(((difflib.SequenceMatcher(None, flat(key), flat(n)).ratio(), n)
                             for n in names), reverse=True)
            best = scored[0] if scored else (0, None)
            second = scored[1][0] if len(scored) > 1 else 0
            if best[0] < RATIO or best[0] - second < MARGIN:
                # No close match at all. That is a restructure — headlines
                # merged or rewritten wholesale. It is provably dead ONLY when
                # every headline at this stop already carries links, i.e. there
                # is no headline left that this key could have been meant for.
                if all_linked.get(sid):
                    acts.pop(key)
                    dead += 1
                    print(f'  dead         {sid}: {key[:64]!r} '
                          f'(every headline at this stop is already linked)')
                else:
                    unmatched += 1
                    print(f'  UNMATCHED    {sid}: {key[:64]!r}  (best {best[0]:.2f})')
            elif best[1] in acts:
                # The headline was reworded AND re-researched under its new
                # text. The old key is dead weight, not lost work — the page
                # already carries the newer entry. Drop it.
                acts.pop(key)
                superseded += 1
                print(f'  superseded {best[0]:.2f} {sid}: {key[:52]!r}\n            (page has {best[1][:52]!r})')
            else:
                acts[best[1]] = acts.pop(key)
                reworded += 1
                print(f'  reworded {best[0]:.2f}  {sid}: {key[:54]!r}\n            -> {best[1][:54]!r}')

    print(f'\n{punct} punctuation-only, {reworded} re-attached to a reworded headline, '
          f'{superseded} superseded, {dead} dead after a restructure, '
          f'{unmatched} left alone')
    if write:
        DB.write_text(json.dumps(db, ensure_ascii=False, indent=2) + '\n')
        print('written to links_db.json')
    else:
        print('(dry run — pass --write to save)')


if __name__ == '__main__':
    main()

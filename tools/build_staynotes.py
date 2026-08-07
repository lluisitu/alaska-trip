#!/usr/bin/env python3
"""
Clean up the stay-strategy notes and sort them into the boxes they belong in.

    cd tools && python3 build_staynotes.py

The section looked like filler, and on the stops where it opens with "**Trimmed
8 nights to 4**" it reads like filler — the asterisks are markdown that nothing
ever rendered, and the sentence describes an edit that was applied months ago.
But that is a handful of bullets out of 628 across 153 stops, and the rest is
the operational detail that is genuinely hard to reconstruct later: which
campground loop takes 50-amp, which spur turns to clay when wet, where the
bison walk, which pad has to be confirmed before the coach commits to it.

So this does not delete the section. It fixes what made it look like filler:

  * Renders the bold that was being printed as literal asterisks.
  * Drops the pacing changelog. "Trimmed 10 nights to 8 to fund the Dawson
    shift" is a record of a decision, not advice for the day you arrive; it
    lives in the seasonal-timing write-ups where the reasoning is kept.
  * Drops bullets that only restate the campground research printed directly
    above them on the same card.
  * Tags what survives, so a note about the drive out shows up next to the
    passes and a note about the pad shows up next to the campground, instead
    of all of it landing in one undifferentiated list at the bottom.

Idempotent: re-running finds nothing left to strip.

Standard library only; no network.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'

# Edits already applied to the itinerary. The dashboard shows the itinerary that
# resulted, so restating the edit on the stop card is describing the past.
CHANGELOG = re.compile(
    r'\bTrimmed\b|\bnights? to \d|\bto fund the\b|one-day margin|\bre-?paced\b'
    r'|\bMoved (?:six|~?\d+) days earlier|\bGained a night|\bCut from \d+ nights?\b'
    r'|\bAdded \d+ nights? (?:here|to)\b', re.I)

# Where each surviving bullet belongs.
KIND = [
    ('road',   re.compile(r'\bdo not combine\b|\bin one push\b|longest scheduled|intermediate night'
                          r'|\bunreasonable\b|\bswitchback|\bgrade\b|\bpass is\b|\bunhitch|\bdrop the (?:truck|toad)'
                          r'|\bfuel up\b|\bfill up\b|no services for', re.I)),
    ('season', re.compile(r'\bseasonal|\bopens?\b.{0,20}\b(?:April|May|June|July|Aug|Sep|Oct|Nov|Dec)'
                          r'|\bclosed?\b.{0,25}\b(?:winter|snow|season)|freezing|\bice\b|daylight'
                          r'|\bshoulder season\b', re.I)),
    ('safety', re.compile(r'\bbear|\bbison\b|wildlife|\bmoose\b|\bflash flood|\bavalanche'
                          r'|\bturn around\b|\bdo not let\b|\bnever place\b|\bsafe\b', re.I)),
    ('rig',    re.compile(r'\bcoach\b|\bcamper\b|\bsite\b|\bpad\b|\bhookup|\b50-?amp|\b30-?amp'
                          r'|\bpull-?through|\bback-?in\b|\blength\b|\bdump\b|\bwater\b|\bgenerator'
                          r'|\bslide\b|\btire|\bweigh|\binspect', re.I)),
]


def ex(hh, decl, o='{', c='}'):
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


def words(t):
    return [w for w in re.sub(r'[^a-z0-9 ]', ' ', re.sub(r'[*<][^>]*>?', ' ', t.lower())).split()
            if len(w) > 4]


def research_blob(stop):
    cr = stop.get('campResearch') or {}
    parts = [cr.get('verdict', ''), stop.get('note') or '']
    for o in (cr.get('paid_options') or []) + (cr.get('boondock_options') or []):
        parts.append(json.dumps(o, ensure_ascii=False))
    return set(words(' '.join(parts)))


def kind_of(text):
    for name, pat in KIND:
        if pat.search(text):
            return name
    return 'general'


def clean(stop):
    notes = stop.get('campNotes') or []
    if not notes:
        return None, {'changelog': 0, 'dup': 0, 'bold': 0, 'kept': 0}
    blob = research_blob(stop)
    stats = {'changelog': 0, 'dup': 0, 'bold': 0, 'kept': 0}
    out, seen = [], set()
    for n in notes:
        if isinstance(n, dict):            # already processed by an earlier run
            out.append(n); stats['kept'] += 1; continue
        if CHANGELOG.search(n):
            stats['changelog'] += 1; continue
        w = words(n)
        if w and sum(1 for x in w if x in blob) / len(w) > 0.85:
            stats['dup'] += 1; continue
        key = re.sub(r'\W+', '', n.lower())[:80]
        if key in seen:
            stats['dup'] += 1; continue
        seen.add(key)
        if '**' in n:
            stats['bold'] += 1
        # The asterisks were being printed verbatim; this is the only markdown
        # the notes ever used.
        html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', n).replace('**', '')
        out.append({'t': html.strip(), 'k': kind_of(n)})
        stats['kept'] += 1
    return out, stats


def main():
    h = SRC.read_text()
    stops = json.loads(ex(h, 'const STOPS =', '[', ']'))
    ext_raw = ex(h, 'const EXT_DATA =')
    ext = json.loads(ext_raw)

    total = {'changelog': 0, 'dup': 0, 'bold': 0, 'kept': 0}
    kinds = {}

    def walk(lst):
        changed = 0
        for s in lst:
            new, st = clean(s)
            for k in total:
                total[k] += st[k]
            if new is None:
                continue
            for n in new:
                kinds[n['k']] = kinds.get(n['k'], 0) + 1
            if new != s.get('campNotes'):
                s['campNotes'] = new
                changed += 1
        return changed

    walk(stops)
    walk(ext['STOPS'])

    if total['kept'] == 0:
        sys.exit("!! every stay note was stripped — the filters are too broad")

    h = h.replace(ex(h, 'const STOPS =', '[', ']'),
                  json.dumps(stops, ensure_ascii=False), 1)
    # build_parks.py writes EXT_DATA with indent=1. Writing it compact here made
    # the two scripts reformat the same block back and forth forever, so the
    # publish never reached a stable file. Match its formatting exactly.
    h = h.replace(ext_raw, json.dumps(ext, ensure_ascii=False, indent=1), 1)
    SRC.write_text(h)

    print(f"  kept {total['kept']} stay notes")
    print(f"  dropped {total['changelog']} pacing-changelog bullets and {total['dup']} that "
          f"repeated the research above them")
    print(f"  rendered bold in {total['bold']} that were printing literal asterisks")
    print("  sorted into: " + ' · '.join(f"{k} {v}" for k, v in
                                         sorted(kinds.items(), key=lambda kv: -kv[1])))
    print("wrote", SRC)


if __name__ == '__main__':
    main()

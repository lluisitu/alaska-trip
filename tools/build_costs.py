#!/usr/bin/env python3
"""
Surface what the trip costs to sleep, from the price notes already researched.

    cd tools && python3 build_costs.py

The campground research already carries a price note on 332 of the 409 paid
options — it has simply never been shown as a number. This reads those notes,
pulls out the nightly rate for the option that was actually chosen at each stop
(matched against the stop's `camp` field, falling back to the first priced
option), multiplies by the nights, and totals it.

Two rules govern this file, and they are the whole point of it:

  1. Nothing is invented. A rate only exists where a researched note states one.
     Stops with no stated rate are counted and reported as unpriced, never
     filled in with an average — an average would quietly turn "we don't know"
     into a number someone budgets against.

  2. The total is a range, not a figure. Notes say things like "$17/night (30A)
     or $22/night (50A)", and both ends are kept.

Fuel is deliberately not totalled here. It depends on a mileage figure for this
specific coach that nobody has measured yet, so the dashboard shows the miles
and the arithmetic and lets the reader supply the mpg.

Standard library only; no network.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'

# "$17/night (30A) or $22/night (50A)" -> 17, 22 ; "$15-20/night" -> 15, 20
MONEY = re.compile(r'\$\s?(\d{1,3})(?:\s?[-–—]\s?\$?(\d{1,3}))?')
# Notes that mention a dollar figure but not as a nightly rate for the site.
NOT_A_RATE = re.compile(
    r'entrance fee|per person|/person|per vehicle|day.use|annual|america the beautiful|'
    r'reservation fee|booking fee|deposit|dump (?:station )?fee|shower', re.I)


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


def rate_from(note):
    """Return (lo, hi) nightly dollars, or None. Only the part of the note before
    any 'plus ...' clause is read, so a per-person entrance fee is not mistaken
    for the site rate."""
    if not note:
        return None
    head = re.split(r'\bplus\b|\bin addition\b|;', note, 1)[0]
    if NOT_A_RATE.search(head) and not re.search(r'/\s?night|per night|nightly', head, re.I):
        return None
    hits = MONEY.findall(head)
    if not hits:
        return None
    vals = []
    for lo, hi in hits:
        vals.append(int(lo))
        if hi:
            vals.append(int(hi))
    vals = [v for v in vals if 0 < v <= 300]     # a $2,400 figure is a season pass, not a night
    if not vals:
        return None
    return min(vals), max(vals)


def chosen_option(stop):
    """The option the itinerary actually books, matched on the stop's camp name.
    Falls back to the first option that states a price rather than the first
    option outright, so a stop whose chosen site has no published rate still
    contributes a real researched number from a real alternative — flagged as
    such."""
    cr = stop.get('campResearch') or {}
    opts = cr.get('paid_options') or []
    camp = (stop.get('camp') or '').lower()
    for o in opts:
        n = (o.get('name') or '').lower()
        if n and camp and (n in camp or camp in n):
            if rate_from(o.get('price_note')):
                return o, 'chosen'
    for o in opts:
        if rate_from(o.get('price_note')):
            return o, 'alternative'
    return None, None


def main():
    h = SRC.read_text()
    stops = json.loads(ex(h, 'const STOPS =', '[', ']'))
    ext = json.loads(ex(h, 'const EXT_DATA ='))['STOPS']

    out = {}
    tot_lo = tot_hi = 0
    nights_priced = nights_total = 0
    priced = unpriced = 0
    free_nights = 0

    for s in stops + ext:
        nights = s.get('nights') or 0
        nights_total += nights
        opt, how = chosen_option(s)
        if not opt:
            unpriced += 1
            cr = s.get('campResearch') or {}
            # A stop with no paid option at all but a boondocking option is free,
            # which is a real answer rather than a missing one.
            if (cr.get('boondock_options') and not (cr.get('paid_options') or [])):
                out[s['id']] = {'lo': 0, 'hi': 0, 'nights': nights, 'how': 'boondock',
                                'name': (cr['boondock_options'][0].get('name') or 'dispersed'),
                                'note': 'no paid option researched here — free/dispersed camping'}
                free_nights += nights
            continue
        lo, hi = rate_from(opt.get('price_note'))
        priced += 1
        nights_priced += nights
        tot_lo += lo * nights
        tot_hi += hi * nights
        out[s['id']] = {
            'lo': lo, 'hi': hi, 'nights': nights, 'how': how,
            'name': opt.get('name') or '',
            'note': opt.get('price_note') or '',
            'url': opt.get('source_url') or '',
        }

    summary = {
        'stopsPriced': priced,
        'stopsUnpriced': unpriced,
        'nightsPriced': nights_priced,
        'nightsTotal': nights_total,
        'nightsFree': free_nights,
        'lo': tot_lo, 'hi': tot_hi,
    }

    if nights_priced == 0:
        sys.exit("!! no nightly rates parsed at all — the price-note format must have changed")

    payload = json.dumps({'stops': out, 'summary': summary}, ensure_ascii=False, sort_keys=True)
    decl = re.compile(r'const COSTS = \{.*?\};\n', re.S)
    block = f'const COSTS = {payload};\n'
    if decl.search(h):
        h = decl.sub(lambda _m: block, h, count=1)
    else:
        anchor = 'const PHOTO ='
        assert anchor in h, 'PHOTO declaration missing'
        h = h.replace(anchor, block + '\n' + anchor, 1)
    SRC.write_text(h)

    pct = round(100 * nights_priced / nights_total)
    print(f"  {priced} stops carry a researched nightly rate, {unpriced} do not")
    print(f"  ${tot_lo:,}–${tot_hi:,} for {nights_priced} of {nights_total} nights ({pct}%)")
    print(f"  {nights_total - nights_priced} nights have no researched rate and are NOT estimated")
    print("wrote", SRC)


if __name__ == '__main__':
    main()

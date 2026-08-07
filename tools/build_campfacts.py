#!/usr/bin/env python3
"""
Verified campground facts: real site lengths, Google ratings, and whether the
place is even open on the day you arrive.

    cd tools && python3 build_campfacts.py

Why this exists. The rig-fit extractor reads whatever the original research
wrote down, and for 52 stops that was "no length published". LLuis checked one
of them — Wrangell View in Chitina — and found its booking engine listing every
site individually: "Site 4 · 30/50A · 70ft · Water · Sewage · $65/night". The
information was never missing. It was one click inside a reservation system
that a text search does not reach.

So all 52 were re-researched against the booking engines themselves — Campspot,
ResNexus, Firefly, Newbook, Cloudbeds, goingtocamp, midnrreservations — plus
Google ratings, because a campground the coach fits into and everybody hates is
not actually a good answer.

Three kinds of finding come out of it, and the third is the one that matters:

  * Real site lengths for 36 of the 52, several of them per-site rather than a
    single campground maximum.
  * Google ratings for 43 of the 52. Google Maps itself is unreachable from
    here, so these are Wanderlog's mirror of the Google figure, spot-checked
    against a second source; where no Google-sourced figure existed the rating
    is null rather than a substituted Campendium or Good Sam score, which are
    different user pools entirely.
  * Five bookings that are simply broken: four campgrounds closed on the date
    of arrival, and one that could not be shown to exist at all.

Standard library only; no network.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'
DB = pathlib.Path(__file__).resolve().parent / 'campfacts_db.json'

GOOD_RATING = 4.0      # below this, the card says so and offers the alternative


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


def main():
    h = SRC.read_text()
    db = json.loads(DB.read_text())['stops']
    stops = json.loads(ex(h, 'const STOPS =', '[', ']'))
    ext = json.loads(ex(h, 'const EXT_DATA ='))['STOPS']
    ids = {s['id'] for s in stops + ext}

    bad = [k for k in db if k not in ids]
    if bad:
        sys.exit('!! campfacts references unknown stop ids: ' + ', '.join(bad[:8]))

    # Every stated figure needs a source. An uncited length is worse than none,
    # because a length gets acted on and an absence gets phoned about.
    uncited = [k for k, v in db.items()
               if (v.get('max_site_ft') or v.get('google')) and not v.get('sources')]
    if uncited:
        sys.exit('!! entries state a figure with no source: ' + ', '.join(uncited))

    out, n_len, n_rating, closed, low, alts = {}, 0, 0, [], [], 0
    for sid, v in db.items():
        rec = {
            'camp': v.get('camp'),
            'ft': v.get('max_site_ft'),
            'n40': v.get('sites_40ft_plus'),
            'detail': v.get('site_detail'),
            'phone': v.get('phone'),
            'url': v.get('booking_url'),
            'rate': v.get('rate'),
            'open': v.get('open_on_arrival'),
            'notes': v.get('notes'),
            'sources': v.get('sources') or [],
            'exists': v.get('exists', True),
        }
        if v.get('observed'):
            rec['observed'] = v['observed']
        g = v.get('google') or {}
        if g.get('rating') is not None:
            rec['g'] = g.get('rating'); rec['gn'] = g.get('reviews'); rec['gd'] = g.get('checked')
            n_rating += 1
            if g['rating'] < GOOD_RATING:
                low.append((sid, g['rating'], g.get('reviews')))
        if rec['ft']:
            n_len += 1
        if rec['open'] is False or rec['exists'] is False:
            closed.append((sid, rec['camp']))
        ba = v.get('better_alternative')
        if ba:
            rec['alt'] = {k: ba.get(k) for k in
                          ('name', 'max_site_ft', 'phone', 'url', 'distance_mi', 'why', 'sources')}
            if ba.get('google'):
                rec['alt']['g'] = ba['google'].get('rating')
                rec['alt']['gn'] = ba['google'].get('reviews')
            alts += 1
        out[sid] = rec

    payload = json.dumps({'stops': out, 'good': GOOD_RATING}, ensure_ascii=False, sort_keys=True)
    decl = re.compile(r'const CAMPFACTS = \{.*?\};\n', re.S)
    block = f'const CAMPFACTS = {payload};\n'
    if decl.search(h):
        h = decl.sub(lambda _m: block, h, count=1)
    else:
        anchor = 'const PHOTO ='
        assert anchor in h, 'PHOTO declaration missing'
        h = h.replace(anchor, block + '\n' + anchor, 1)
    SRC.write_text(h)

    print(f"  {len(out)} campgrounds re-researched against their booking engines")
    print(f"     {n_len} now have a real site length · {n_rating} have a Google rating")
    print(f"     {alts} carry a better-rated alternative")
    if low:
        print(f"  rated below {GOOD_RATING}:")
        for sid, r, n in sorted(low, key=lambda x: x[1]):
            print(f"     {sid:<24}{r}  ({n} reviews)")
    if closed:
        print("  !! BOOKED SOMEWHERE CLOSED OR UNVERIFIABLE ON THE ARRIVAL DATE:")
        for sid, camp in closed:
            print(f"     {sid:<24}{camp}")
    print("wrote", SRC)


if __name__ == '__main__':
    main()

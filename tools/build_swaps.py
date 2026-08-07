#!/usr/bin/env python3
"""
Apply the campground replacements — actually change the booking, don't just
suggest it.

    cd tools && python3 build_swaps.py

Four of the stops were booked into campgrounds that are shut on the day of
arrival, one into a park that could not be shown to exist at all, and three
more into places that rate poorly enough to be worth moving. Showing that on
the card and leaving the itinerary pointing at a closed campground is only half
an answer, so this rewrites the plan: the stop's camp, the campground option
list, the booking card, and an issue entry recording what changed and why.

Two stops are deliberately NOT swapped, and they are listed in the same file so
the reasoning is on the record rather than lost:

  * Chitina keeps Wrangell View despite 3.8. The only other hookup park within
    35 miles drops to 30-amp with no sewer, and the rest is tent-only. A bad
    rating at the one place that fits beats a good rating at a place that does
    not.
  * Great Basin keeps Whispering Elms. Border Inn rates 4.0 against 3.9, but
    that listing covers a casino and motel rather than the RV stalls, its sites
    are reported at 40 ft with no margin, and it is 9 miles out of Baker.

Idempotent: a stop already sitting on its replacement is skipped.

Standard library only; no network.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'
DB = pathlib.Path(__file__).resolve().parent / 'swaps_db.json'


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


def option_from(sw):
    """Build a campground option card from the researched replacement."""
    bits = []
    if sw.get('ft'):
        bits.append(f"Sites to {sw['ft']} ft")
    if sw.get('hookups'):
        bits.append(sw['hookups'])
    if sw.get('mi') is not None:
        bits.append(f"{sw['mi']} miles from the stop")
    rig = '; '.join(bits) + '.' if bits else ''
    if sw.get('g') is not None:
        rig += f" Google {sw['g']}" + (f" from {sw['gn']} reviews." if sw.get('gn') else ".")
    return {
        'name': sw['name'],
        'type': sw.get('type') or 'Private RV Resort/Park',
        'rig_note': (rig + ' ' + (sw.get('why') or '')).strip(),
        'price_note': sw.get('rate') or '',
        'pros': sw.get('why') or '',
        'cons': f"Replaces {sw['replace']}. {sw['reason']} Confirm the site length and the "
                f"dates by phone before you rely on it.",
        'source_url': (sw.get('sources') or [sw.get('url')])[0] or '',
    }


def main():
    h = SRC.read_text()
    db = json.loads(DB.read_text())
    swaps, kept = db['swaps'], db.get('kept', [])

    stops_raw = ex(h, 'const STOPS =', '[', ']')
    stops = json.loads(stops_raw)
    ext_raw = ex(h, 'const EXT_DATA =')
    ext = json.loads(ext_raw)
    bk_raw = ex(h, 'const BOOKINGS =', '[', ']')
    bookings = json.loads(bk_raw)
    iss_raw = ex(h, 'const ISSUES =', '[', ']')
    issues = json.loads(iss_raw)

    by_id = {s['id']: s for s in stops}
    by_id.update({s['id']: s for s in ext['STOPS']})
    bk_by = {b['id']: b for b in bookings}
    done, skipped, missing = [], [], []

    for sw in swaps:
        s = by_id.get(sw['id'])
        if not s:
            missing.append(sw['id']); continue
        if (s.get('camp') or '').startswith(sw['name'][:18]):
            skipped.append(sw['id']); continue

        s['camp'] = sw['name']
        cr = s.setdefault('campResearch', {'verdict': '', 'paid_options': [], 'boondock_options': []})
        opts = cr.setdefault('paid_options', [])
        # The old pick stays on the card — it is why the new one is there, and
        # deleting it would erase the evidence that the swap was needed.
        opts[:] = [o for o in opts if not (o.get('name') or '').startswith(sw['name'][:18])]
        opts.insert(0, option_from(sw))
        cr['verdict'] = (f"Moved to {sw['name']}. {sw['reason']} "
                         + (sw.get('why') or '')
                         + (f" Call {sw['phone']} to confirm." if sw.get('phone') else ''))

        b = bk_by.get(sw['id'])
        if b:
            b['camp'] = sw['name']
            b['what'] = f"RV site, {s.get('nights', '?')} nights — 40ft Class A + towed truck"
            if sw.get('phone'):
                b['phone'] = sw['phone']
                b['how'] = 'call'
                b['howText'] = f"Call {sw['phone']} to book — this replaced a campground that was closed or unverifiable."
            if sw.get('url'):
                b['url'] = sw['url']
                b['system'] = 'direct with the park'
            # A window inherited from the old campground is worse than none.
            b['opensISO'] = None
            b['opensLocalTime'] = None
            b['confidence'] = 'unknown'

        issues.append({
            'id': f"swap-{sw['id']}",
            'category': 'resolved',
            'severity': 'red',
            'stop_id': sw['id'],
            'stop_name': s.get('name', sw['id']),
            'issue': f"{sw['replace']} could not be used",
            'analysis': sw['reason'],
            'solution': (f"APPLIED — moved to {sw['name']}"
                         + (f", rated {sw['g']}" + (f" from {sw['gn']} reviews" if sw.get('gn') else '') if sw.get('g') is not None else '')
                         + (f", sites to {sw['ft']} ft" if sw.get('ft') else '')
                         + (f", {sw['mi']} miles away" if sw.get('mi') is not None else '')
                         + (f". Call {sw['phone']}" if sw.get('phone') else '')
                         + (f". {sw['url']}" if sw.get('url') else '')),
        })
        done.append(sw)

    if missing:
        sys.exit('!! swaps reference unknown stops: ' + ', '.join(missing))

    if done:
        h = h.replace(stops_raw, json.dumps(stops, ensure_ascii=False), 1)
        h = h.replace(ext_raw, json.dumps(ext, ensure_ascii=False, indent=1), 1)
        h = h.replace(bk_raw, json.dumps(bookings, ensure_ascii=False), 1)
        h = h.replace(iss_raw, json.dumps(issues, ensure_ascii=False), 1)

    payload = json.dumps({'kept': kept}, ensure_ascii=False, sort_keys=True)
    decl = re.compile(r'const KEPT_CAMPS = \{.*?\};\n', re.S)
    block = f'const KEPT_CAMPS = {payload};\n'
    if decl.search(h):
        h = decl.sub(lambda _m: block, h, count=1)
    else:
        h = h.replace('const PHOTO =', block + '\nconst PHOTO =', 1)
    SRC.write_text(h)

    print(f"  {len(done)} campgrounds replaced, {len(skipped)} already on the new pick")
    for sw in done:
        star = f"★{sw['g']}" if sw.get('g') is not None else 'no rating'
        print(f"     {sw['id']:<22}{sw['replace'][:30]:<32}→ {sw['name'][:38]}  {star}")
    for k in kept:
        print(f"  kept {k['id']:<19}{k['camp'][:38]}")
    print("wrote", SRC)


if __name__ == '__main__':
    main()

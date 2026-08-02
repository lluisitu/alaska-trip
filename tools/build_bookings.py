#!/usr/bin/env python3
"""
Regenerate the Booking Board from the current itinerary.

    cd tools && python3 build_bookings.py

Why this has to be a build step, not hand-maintained data: every booking card
carries the arrival date of its stop, and the date the reservation window opens
is derived from it. Move a stop and the card silently keeps the old arrival AND
the old alarm date. That is exactly what happened after the seasonal-timing
work - 47 of 131 cards were pointing at dates the trip no longer used, including
Denali, which said "arrives Jul 3" when the stay had moved to Jul 29.

So: arrival, nights and the opening date are all recomputed from STOPS here, and
this exits loudly if a booking refers to a stop that no longer exists.

It also derives the two things the card should lead with - WHAT you are booking
and HOW you book it - so the card can say that in one line instead of burying it
in a paragraph of prose.

Standard library only; no network.
"""
import json, pathlib, re, sys, datetime as dt

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'
D = dt.date.fromisoformat

# The rig every one of these bookings has to fit.
RIG = '40ft Class A + towed truck'


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


def minus_months(iso, months):
    """Subtract whole months, clamping the day (Mar 31 - 1 month -> Feb 28/29)."""
    d = D(iso)
    y, m = d.year, d.month - months
    while m <= 0:
        m += 12; y -= 1
    day = d.day
    while day > 1:
        try:
            return dt.date(y, m, day).isoformat()
        except ValueError:
            day -= 1
    return dt.date(y, m, 1).isoformat()


PHONE = re.compile(r'(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\b\d{3})[\s.-]?\d{3}[\s.-]?\d{4}\b')
RESERVED_SYSTEMS = {'first-come', 'walk-up / private'}


def derive(b, stop):
    """Work out what is actually being booked and how you book it."""
    nights = stop['nights']
    b['arrive'] = stop['arrive']
    b['depart'] = stop['depart']
    b['nights'] = nights

    # Every one of these is a place to park the coach - none are tours or tickets -
    # so say so plainly and put the number that matters (nights, and the rig) up front.
    b['what'] = f"RV site, {nights} night{'' if nights == 1 else 's'} — {RIG}"

    sysname = (b.get('system') or '').strip()
    phone = PHONE.search(b.get('note') or '')
    b['phone'] = phone.group(0).strip() if phone else None

    if sysname == 'first-come':
        b['how'] = 'firstcome'
        b['howText'] = 'First-come, first-served — no reservation exists. Arrive early in the day.'
    elif sysname in RESERVED_SYSTEMS or not sysname:
        b['how'] = 'call'
        b['howText'] = (f"Call to book — {b['phone']}" if b['phone']
                        else 'Private park — call to book; no online window published.')
    else:
        b['how'] = 'reserve'
        when = ''
        if b.get('opensISO'):
            when = ' the day the window opens'
            if b.get('opensLocalTime'):
                when += f" at {b['opensLocalTime']}"
        b['howText'] = f"Reserve online through {sysname}{when}."
    return b


def main():
    h = SRC.read_text()
    S = {s['id']: s for s in json.loads(ex(h, 'const STOPS =', '[', ']'))}
    E = {s['id']: s for s in json.loads(ex(h, 'const EXT_DATA ='))['STOPS']}
    raw = ex(h, 'const BOOKINGS =', '[', ']')
    B = json.loads(raw)

    out, moved, dropped, redated = [], 0, [], 0
    for b in B:
        src = S if b.get('trip') == 'main' else E
        stop = src.get(b['id']) or S.get(b['id']) or E.get(b['id'])
        if not stop:
            dropped.append(b['id'])
            continue
        if b.get('arrive') != stop['arrive']:
            moved += 1
            print(f"   re-dated {b['id']:<24} {b.get('arrive')} -> {stop['arrive']}")
        derive(b, stop)
        # The alarm date is derived, never stored by hand.
        if b.get('leadMonths'):
            new_open = minus_months(stop['arrive'], b['leadMonths'])
            if new_open != b.get('opensISO'):
                redated += 1
            b['opensISO'] = new_open
        out.append(b)

    print(f"\n  {len(out)} bookings, {moved} arrival dates corrected, "
          f"{redated} reservation-opening dates recomputed")
    if dropped:
        print(f"  dropped {len(dropped)} booking(s) for stops that no longer exist: {dropped}")
    counts = {}
    for b in out:
        counts[b['how']] = counts.get(b['how'], 0) + 1
    print(f"  how to book: {counts}")

    # Sanity: nothing may be left pointing at a date the itinerary does not use.
    for b in out:
        src = S if b.get('trip') == 'main' else E
        stop = src.get(b['id']) or S.get(b['id']) or E.get(b['id'])
        if b['arrive'] != stop['arrive']:
            sys.exit(f"!! {b['id']} still stale after rebuild")
        if b.get('opensISO') and b['opensISO'] >= b['arrive']:
            sys.exit(f"!! {b['id']} opens {b['opensISO']} after it arrives {b['arrive']}")

    h = h.replace(raw, json.dumps(out, ensure_ascii=False), 1)
    SRC.write_text(h)
    print("wrote", SRC)


if __name__ == '__main__':
    main()

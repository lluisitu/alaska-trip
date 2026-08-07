#!/usr/bin/env python3
"""
Compute the light at every stop, for the dates the trip is actually there.

    cd tools && python3 build_light.py

A shot list is only half the answer. The other half is arithmetic nobody should
be doing on the road: when the sun rises and sets at THIS latitude on THIS date,
which compass direction it rises and sets from, how long golden hour lasts, and
whether the moon will be up and full enough to wreck a dark-sky exposure.

That matters more on this trip than most. Fairbanks in late June has no
astronomical night at all, so the aurora is simply not photographable; Dawson
City in early September has it back. A west-facing viewpoint is a sunset shot in
December and a nothing shot in June, because the sun sets 60 degrees further
north. None of that is guessable, and all of it is computable offline.

Algorithms: NOAA solar position (the same one behind their published calculator)
and a standard Meeus lunar phase approximation. Accurate to well under a minute
for sunrise and sunset, which is far tighter than any use here needs.

Standard library only; no network. Times are LOCAL STANDARD time at the stop's
longitude — deliberately not adjusted for daylight saving, because DST rules vary
by jurisdiction and a wrong hour is worse than a stated convention. The dashboard
says so on the card.
"""
import json, math, pathlib, sys, datetime as dt

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'
D = dt.date.fromisoformat
RAD = math.pi / 180.0


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


def julian(d):
    return d.toordinal() + 1721424.5


def solar(jd):
    """Return (declination deg, equation of time minutes) for a Julian day."""
    t = (jd - 2451545.0) / 36525.0
    L0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    M = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    C = (math.sin(M * RAD) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(2 * M * RAD) * (0.019993 - 0.000101 * t)
         + math.sin(3 * M * RAD) * 0.000289)
    true_long = L0 + C
    omega = 125.04 - 1934.136 * t
    lam = true_long - 0.00569 - 0.00478 * math.sin(omega * RAD)
    eps0 = (23 + (26 + ((21.448 - t * (46.815 + t * (0.00059 - t * 0.001813)))) / 60) / 60)
    eps = eps0 + 0.00256 * math.cos(omega * RAD)
    decl = math.asin(math.sin(eps * RAD) * math.sin(lam * RAD)) / RAD
    y = math.tan(eps / 2 * RAD) ** 2
    eot = 4 * (y * math.sin(2 * L0 * RAD)
               - 2 * e * math.sin(M * RAD)
               + 4 * e * y * math.sin(M * RAD) * math.cos(2 * L0 * RAD)
               - 0.5 * y * y * math.sin(4 * L0 * RAD)
               - 1.25 * e * e * math.sin(2 * M * RAD)) / RAD
    return decl, eot


def hour_angle(lat, decl, zenith):
    """Hour angle in degrees at which the sun hits `zenith`.

    cos(HA) = (cos Z - sin(lat) sin(dec)) / (cos(lat) cos(dec)).

    Two no-solution cases, and getting them the right way round matters:
      c >  1  the sun never climbs to that altitude — it stays BELOW the
              threshold all day. For the sunrise threshold that is polar night;
              for the -18 threshold it means dark around the clock.
      c < -1  the sun never drops to that altitude — it stays ABOVE the
              threshold all night. For the sunrise threshold that is midnight
              sun; for the -18 threshold it means no astronomical darkness at
              all, which is why the aurora is unphotographable in an Alaskan
              June no matter how clear the sky is.
    """
    c = ((math.cos(zenith * RAD) - math.sin(lat * RAD) * math.sin(decl * RAD))
         / (math.cos(lat * RAD) * math.cos(decl * RAD)))
    if c > 1: return 'below'    # never rises to it
    if c < -1: return 'above'   # never sinks to it
    return math.acos(c) / RAD


def events(lat, lng, date):
    """Local-standard-time events at a stop, as fractional hours."""
    decl, eot = solar(julian(date) + 0.5)
    noon = 12.0 - eot / 60.0            # local apparent noon, local mean solar time
    out = {'solarNoon': noon, 'declination': round(decl, 2)}
    # zenith angles: 90.833 = sunrise/sunset (refraction + solar disc), 96 = civil,
    # 102 = nautical, 108 = astronomical dark. Golden hour ends at +6 altitude = 84.
    for key, z in (('sun', 90.833), ('civil', 96.0), ('nautical', 102.0),
                   ('astro', 108.0), ('golden', 84.0)):
        ha = hour_angle(lat, decl, z)
        if isinstance(ha, str):
            out[key] = ha                       # 'below' = never rises to it, 'above' = never sinks to it
        else:
            out[key] = (noon - ha / 15.0, noon + ha / 15.0)
    return out


def azimuth(lat, decl, ha_deg):
    """Compass bearing of the sun at a given hour angle."""
    ha = ha_deg * RAD
    lat_r, dec_r = lat * RAD, decl * RAD
    alt = math.asin(math.sin(lat_r) * math.sin(dec_r) + math.cos(lat_r) * math.cos(dec_r) * math.cos(ha))
    az = math.atan2(-math.sin(ha), math.tan(dec_r) * math.cos(lat_r) - math.sin(lat_r) * math.cos(ha))
    return (az / RAD) % 360, alt / RAD


def compass(deg):
    pts = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
           'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    return pts[int((deg + 11.25) % 360 / 22.5)]


def moon_phase(date):
    """Illuminated fraction and phase name, Meeus low-precision."""
    jd = julian(date) + 0.5
    t = (jd - 2451545.0) / 36525.0
    D_ = (297.8501921 + 445267.1114034 * t) % 360
    M = (357.5291092 + 35999.0502909 * t) % 360
    Mp = (134.9633964 + 477198.8675055 * t) % 360
    i = (180 - D_ - 6.289 * math.sin(Mp * RAD) + 2.100 * math.sin(M * RAD)
         - 1.274 * math.sin((2 * D_ - Mp) * RAD) - 0.658 * math.sin(2 * D_ * RAD)
         - 0.214 * math.sin(2 * Mp * RAD) - 0.110 * math.sin(D_ * RAD)) % 360
    frac = (1 + math.cos(i * RAD)) / 2
    age = ((jd - 2451550.1) / 29.530588853) % 1
    name = ('new moon' if frac < 0.04 else 'full moon' if frac > 0.96 else
            ('waxing' if age < 0.5 else 'waning') + (' crescent' if frac < 0.35 else
             ' gibbous' if frac > 0.65 else ' quarter'))
    return round(frac, 2), name


def hm(x):
    if x is None: return None
    h = int(x) % 24; m = int(round((x - int(x)) * 60))
    if m == 60: h, m = (h + 1) % 24, 0
    return f"{h:02d}:{m:02d}"


def zone_offset(tz, date):
    """UTC offset in hours for an IANA zone on a given date, DST included.

    zoneinfo is standard library from Python 3.9 and reads the system tz
    database, so this needs no pip install and no network. If a machine has
    neither, the caller falls back to solar time and says so rather than
    printing a clock time that is quietly wrong.
    """
    try:
        from zoneinfo import ZoneInfo
        import datetime as _dt
        off = _dt.datetime(date.year, date.month, date.day, 12,
                           tzinfo=ZoneInfo(tz)).utcoffset()
        return off.total_seconds() / 3600.0
    except Exception:
        return None


def to_clock(solar_hours, lng, tz, date):
    """Local mean solar time at a longitude -> the time on the wall clock.

    events() works in local mean solar time, which is what the astronomy wants
    and NOT what anybody reads off a phone. At Craters of the Moon the gap is
    an hour and 34 minutes: solar sunset 19:07, actual sunset 20:41 MDT. Every
    golden-hour time on every card was showing the solar figure, so the whole
    light box was up to two hours out - and golden hour is exactly the thing
    you set an alarm for.

        local mean solar time = UTC + lng/15
        wall clock            = UTC + zone offset
    """
    if solar_hours is None: return None
    off = zone_offset(tz, date)
    if off is None: return solar_hours
    return solar_hours - lng / 15.0 + off


# Geomagnetic latitude, not geographic, decides whether you are under the auroral
# oval — the oval is centred on the magnetic pole over northern Canada, which is why
# Dawson City beats Fairbanks despite being further south. IGRF dipole for ~2027.
GEOMAG_POLE = (80.7, -72.7)


def geomag_lat(lat, lng):
    la, lo = lat * RAD, lng * RAD
    pa, po = GEOMAG_POLE[0] * RAD, GEOMAG_POLE[1] * RAD
    s = math.sin(pa) * math.sin(la) + math.cos(pa) * math.cos(la) * math.cos(lo - po)
    return math.asin(max(-1.0, min(1.0, s))) / RAD


def aurora(lat, lng, arrive, depart):
    """Is the aurora actually catchable here, on these dates?

    Three things have to line up and the dashboard should say which one fails.

    Darkness uses the NAUTICAL threshold (sun 12 degrees down), not astronomical.
    That is the honest bar for aurora: Fairbanks' own published season opens on
    August 21, a fortnight before -18 darkness returns there, and people plainly
    do see it in that fortnight. Using -18 would report "impossible" for nights
    that work.
    """
    gm = geomag_lat(lat, lng)
    nights = []
    d = D(arrive)
    while d < D(depart):
        ev = events(lat, lng, d)
        na = ev['nautical']
        hrs = 0.0 if na == 'above' else 24.0 if na == 'below' else 24 - (na[1] - na[0])
        frac, _ = moon_phase(d)
        nights.append({'date': d.isoformat(), 'darkHours': round(hrs, 1), 'moon': frac})
        d += dt.timedelta(days=1)
    usable = [n for n in nights if n['darkHours'] >= 1.0]
    prime = [n for n in usable if n['moon'] < 0.35]
    if gm >= 60:
        band, band_note = 'oval', 'under or beside the auroral oval — visible on any active night'
    elif gm >= 55:
        band, band_note = 'fringe', 'south of the oval — needs a moderate storm (Kp 4-5)'
    elif gm >= 50:
        band, band_note = 'storm', 'only during a strong storm (Kp 6+), low on the northern horizon'
    else:
        band, band_note = 'no', 'too far south to be worth planning around'
    if band == 'no' or not usable:
        verdict = 'none'
    elif band == 'oval' and prime:
        verdict = 'prime'
    elif band == 'oval':
        verdict = 'good'
    elif prime:
        verdict = 'chance'
    else:
        verdict = 'unlikely'
    return {'geomagLat': round(gm, 1), 'band': band, 'bandNote': band_note,
            'verdict': verdict, 'nights': len(nights), 'usableNights': len(usable),
            'primeNights': len(prime),
            'maxDarkHours': max([n['darkHours'] for n in nights], default=0),
            'best': sorted(prime, key=lambda n: (n['moon'], -n['darkHours']))[:4]}


def describe(lat, lng, arrive, depart, tz=None):
    """Light at the midpoint of the stay — the representative day.

    Every time that comes out of here is a WALL CLOCK time in the stop's own
    timezone, converted from the local mean solar time the astronomy works in.
    """
    a, b = D(arrive), D(depart)
    mid = a + (b - a) // 2
    ev = events(lat, lng, mid)
    decl = ev['declination']
    clk = lambda x: to_clock(x, lng, tz, mid) if tz else x
    out = {'date': mid.isoformat(), 'declination': decl}
    if tz:
        out['tz'] = tz
        if zone_offset(tz, mid) is None:
            out['tzWarning'] = ('No timezone database on the build machine — these times are local '
                                'solar time, not clock time.')
    if isinstance(ev['sun'], tuple):
        rise, set_ = ev['sun']
        ha = (rise - ev['solarNoon']) * 15.0
        az_r, _ = azimuth(lat, decl, ha)
        az_s, _ = azimuth(lat, decl, -ha)
        out['sunrise'], out['sunset'] = hm(clk(rise)), hm(clk(set_))
        out['sunriseAz'], out['sunsetAz'] = round(az_r), round(az_s)
        out['sunriseDir'], out['sunsetDir'] = compass(az_r), compass(az_s)
        out['dayLength'] = round((set_ - rise), 1)
        if isinstance(ev['golden'], tuple):
            g0, g1 = ev['golden']
            out['goldenMorning'] = [hm(clk(rise)), hm(clk(g0))]
            out['goldenEvening'] = [hm(clk(g1)), hm(clk(set_))]
            out['goldenMinutes'] = round((g0 - rise) * 60)
    elif ev['sun'] == 'above':
        out['sunrise'] = out['sunset'] = None
        out['note'] = 'Midnight sun — the sun never sets.'
        out['dayLength'] = 24.0
    else:
        out['sunrise'] = out['sunset'] = None
        out['note'] = 'Polar night — the sun never rises.'
        out['dayLength'] = 0.0
    # Darkness: the thing that decides whether stars or aurora are photographable.
    if ev['astro'] == 'above':
        out['darkness'] = 'none'
        out['darkNote'] = ('No astronomical darkness at all on these dates — the sun never gets 18 degrees '
                           'below the horizon, so stars and aurora are not photographable here however '
                           'clear the sky is.')
    elif ev['astro'] == 'below':
        out['darkness'] = 'full'
        out['darkNote'] = 'Dark around the clock.'
    else:
        d0, d1 = ev['astro']
        hours = (24 - (d1 - d0))
        out['darkness'] = 'partial'
        out['darkStart'], out['darkEnd'] = hm(clk(d1)), hm(clk(d0))
        out['darkHours'] = round(hours, 1)
        out['darkNote'] = (f"Astronomical dark {hm(clk(d1))} to {hm(clk(d0))} — {hours:.1f} hours."
                           if hours >= 1 else
                           f"Barely {hours*60:.0f} minutes of true darkness — marginal for stars.")
    # Moon, at the same midpoint, plus the darkest night of the stay.
    best, bestfrac = None, 2.0
    dd = a
    while dd < b:
        f, _ = moon_phase(dd)
        if f < bestfrac: bestfrac, best = f, dd
        dd += dt.timedelta(days=1)
    f, name = moon_phase(mid)
    out['moonFrac'], out['moonPhase'] = f, name
    if best:
        out['darkestNight'] = best.isoformat()
        out['darkestFrac'] = bestfrac
    out['aurora'] = aurora(lat, lng, arrive, depart)
    return out


def main():
    h = SRC.read_text()
    S = json.loads(ex(h, 'const STOPS =', '[', ']'))
    EXT = json.loads(ex(h, 'const EXT_DATA ='))
    E = EXT['STOPS']
    light = {}
    warn = []
    for stops in (S, E):
        for s in stops:
            if not s['nights']: continue
            try:
                light[s['id']] = describe(s['lat'], s['lng'], s['arrive'], s['depart'], s.get('tz'))
            except Exception as exc:
                warn.append(f"{s['id']}: {exc}")
    if warn:
        sys.exit('!! light computation failed for: ' + '; '.join(warn))

    nodark = [k for k, v in light.items() if v['darkness'] == 'none']
    midnight = [k for k, v in light.items() if v.get('note', '').startswith('Midnight')]
    print(f"  computed light for {len(light)} stops")
    print(f"  no astronomical darkness at all: {len(nodark)} stops")
    for k in nodark[:12]:
        print(f"     {k:<22}{light[k]['date']}  day {light[k]['dayLength']}h")
    if midnight:
        print(f"  midnight sun: {midnight}")
    short = sorted(light.items(), key=lambda kv: kv[1]['dayLength'])[:3]
    print("  shortest days:", [(k, v['dayLength']) for k, v in short])
    au = [(k, v['aurora']) for k, v in light.items() if v['aurora']['verdict'] in ('prime', 'good')]
    au.sort(key=lambda kv: (-kv[1]['geomagLat'], -kv[1]['primeNights']))
    print(f"  aurora — {len(au)} stops under or beside the oval with usable darkness:")
    for k, a in au:
        print(f"     {k:<22}geomag {a['geomagLat']:>5.1f}  {a['usableNights']:>2}/{a['nights']} usable nights, "
              f"{a['primeNights']} with a dark moon  ({a['verdict']})")

    decl = 'const LIGHT ='
    payload = json.dumps(light, ensure_ascii=False)
    if decl in h:
        h = h.replace(ex(h, decl), payload, 1)
    else:
        # Must be declared BEFORE the card renderers. They self-invoke the moment
        # they are defined, and `typeof LIGHT` on a const still in its temporal
        # dead zone throws a ReferenceError rather than returning "undefined" —
        # which silently kills renderCards and leaves the page with no cards at all.
        anchor = 'const HIGHLIGHTS_BY_LEG ='
        assert anchor in h, 'anchor missing'
        h = h.replace(anchor, f'const LIGHT = {payload};\n\n' + anchor, 1)
    SRC.write_text(h)
    print('wrote', SRC)


if __name__ == '__main__':
    main()

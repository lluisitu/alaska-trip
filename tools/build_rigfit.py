#!/usr/bin/env python3
"""
Work out, per campground, whether the coach actually fits — and say where the
number came from.

    cd tools && python3 build_rigfit.py

The campground research states a length somewhere in 244 of the 332 paid
options, and until now none of it was on the card. The obvious fix — grep for
a number followed by "ft" — is wrong often enough to be dangerous, for three
reasons this script exists to handle:

1. Most of those numbers are OUR rig, not the site's limit. "Call to confirm a
   40ft coach + toad can be accommodated" contains "40ft" and says nothing
   about the site. Self-references are stripped before anything else runs.

2. A posted limit and a crowdsourced observation are different kinds of fact.
   "Maximum site length listed as 60 ft" is a rule. "Campendium's longest
   reported rig is only 20ft" is the largest rig that happened to review the
   place — it is not a limit, and reading it as one would reject campgrounds
   that are fine. Both are useful; they are labelled differently and the posted
   one always wins.

3. Ranges and tiers mean "some sites", not "all sites". "Bronze (≤35ft),
   Gold/Platinum (≤72ft)" fits the coach only if you book the right tier, so
   the verdict says so rather than reporting 72 and leaving you to discover the
   Bronze site you were assigned.

The number that matters is 40 ft — the coach on its own. A posted site length
is the SITE, and almost every park has overflow or side parking for a tow
vehicle, so a 40 ft limit is a fit, not a squeeze. The 60 ft combined figure
only applies where the research says the limit itself covers the tow vehicle:
"combined length", "RV + tow", "total length including toad". Those are called
out separately, because that is the case where 40 ft is genuinely not enough.

Getting this backwards was the first version's mistake: it measured everything
against 60 ft, so a park posting exactly 40 ft — which is fine — came out as
"tight", and 45 ft came out as "park the toad separately" when 45 ft of site is
simply a comfortable fit.

Nothing is inferred where nothing is stated. 274 options get no verdict at all,
and the card says the limit is not published rather than guessing one.

Standard library only; no network.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'

COACH_FT = 40      # the motorhome on its own
COMBO_FT = 60      # coach plus the towed 4x4

NUM = r'(\d{2,3})\s*-?\s*(?:ft|feet|foot|\')'

# Phrases describing OUR rig, stripped first — "confirm a 40ft coach fits" is
# not a 40 ft site limit.
#
# The first version stripped ANY "<number>ft rig", which threw away other
# people's rigs too: at Honey Flat, "One reported 43ft rig fit fine" was the
# single most useful sentence on the card and it was being deleted before the
# extractor ever saw it. Our coach is 40 ft and only 40 ft, so the number has to
# match to be ours — any other figure is somebody else's rig or the site's
# limit, and both are worth keeping.
OURS = re.compile(
    r'(?<!up to )(?<!up to a )\b40\s*-?\s*(?:ft|feet|foot|\')\s*'
    r'(?=\+?\s*(?:class\s*a|coach|motorhome|rv|rig|toad|tow\b|towed|4x4)\b)'
    r'|(?:for|fits?|bringing|with|your|our|this)\s+(?:a|the|your|our|this)?\s*'
    r'\d{2,3}\s*-?\s*(?:ft|feet|foot|\')\s*(?:coach|class\s*a|motorhome|rig|rv)\b',
    re.I)

POSTED = [
    re.compile(r'max(?:imum)?(?:\s+(?:rv|rig|vehicle|site|combined|pull-?through))?\s+length[^.;]{0,30}?' + NUM, re.I),
    re.compile(r'(?:sites?|rigs?|pads?|spaces?|pull-?throughs?|capacity|specs?)\s+'
               r'(?:list\w*\s+)?(?:rated\s+)?(?:capacity\s+)?(?:up\s+to|to)\s+~?' + NUM, re.I),
    re.compile(r'accommodat\w+\s+(?:rigs?\s+)?up\s+to\s+~?' + NUM, re.I),
    re.compile(NUM + r'\s*(?:max(?:imum)?|limit|cap)\b', re.I),
    re.compile(r'(?:claims?|states?|says?)\s+(?:a\s+)?' + NUM + r'\s*(?:cap|limit|max)', re.I),
    re.compile(r'(?:limit(?:ed)?\s+to|no\s+(?:rigs?|vehicles?)\s+over)\s+~?' + NUM, re.I),
    re.compile(r'(?:listed|lists|published|posted|rated|confirmed)[^.;]{0,30}?' + NUM + r'[^.;]{0,15}?(?:max|limit|length)', re.I),
    re.compile(r'max(?:imum)?\s+site\s+' + NUM, re.I),
    # "back-in sites max 35ft motorhomes" — a limit with no word "length" in it.
    re.compile(r'max(?:imum)?\s+' + NUM, re.I),
    re.compile(r'(?:motorhomes?|coaches|rvs?|class\s*a)\s+(?:up\s+to|to)\s+~?' + NUM, re.I),
    re.compile(r'take\s+(?:motorhomes?|rigs?|rvs?)\s+up\s+to\s+~?' + NUM, re.I),
    re.compile(r'≤\s*' + NUM, re.I),                      # tier notation: Gold (≤72ft)
    re.compile(r'sites?\s+(?:are|ranging|range)\s+\d{2,3}\s*-\s*' + NUM, re.I),
]
# "sites can accommodate RVs that are 12+ metres (40+ feet)" is not a maximum —
# it is the operator saying rigs of at least that size are welcome. Treated as a
# floor, which is positive evidence of fit and must never be read as a cap.
ATLEAST = re.compile(r'accommodat\w*[^.;]{0,40}?(\d{2,3})\s*\+\s*(?:ft|feet|foot)'
                     r'|(\d{2,3})\s*\+\s*(?:ft|feet|foot)[^.;]{0,25}?(?:rigs?|rvs?|welcome)', re.I)
REPORTED = [
    re.compile(r'longest\s+reported[^.;]{0,35}?' + NUM, re.I),
    re.compile(r'(?:one|a)\s+reported\s+' + NUM, re.I),
    re.compile(r'reported[^.;]{0,25}?' + NUM + r'[^.;]{0,25}?\bfit', re.I),
    re.compile(r'reviewers?[^.;]{0,45}?' + NUM, re.I),
    re.compile(r'a\s+' + NUM + r'[^.;]{0,40}?(?:fit|confirmed)', re.I),
]
# The research says so itself often enough to just believe it.
CONFLICT = re.compile(r'conflicting|sources? (?:differ|disagree)|another source|but another|disputed', re.I)
UNPUBLISHED = re.compile(r'not (?:published|stated|listed|verifiable|specified|confirmed)|'
                         r'(?:no|without) (?:published|posted|stated) (?:max|length)|unpublished', re.I)
# Where the researcher stated the conclusion outright, take it. They read the
# whole page; a regex reading one sentence of their summary should not overrule
# them. This is what stops "just a few sites up to 35ft — still shorter than
# your rig" being softened into "book a long one" when there is no long one.
SAYS_NO = re.compile(r'too short|won\'t fit|will not fit|not a fit|does not fit|'
                     r'shorter than (?:your|the) (?:rig|coach)|not suitable for (?:a |your )?40', re.I)
# The number applies to some sites, not the whole campground.
SOME = re.compile(r'≤|ranging|range\b|tiers?\b|a few sites|some sites|limited availability|'
                  r'select sites|longest sites|certain sites|only .{0,12}sites|'
                  r'site classes|classes by size|by name, not a generic|sites? #|'
                  r'book a .{0,30}site by name', re.I)


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


def hits(pats, text):
    out = set()
    for p in pats:
        for m in p.findall(text):
            v = int(m if isinstance(m, str) else m[0])
            if 15 <= v <= 200:
                out.add(v)
    return sorted(out)


# The limit covers the tow vehicle too — the only case where 60 ft is the bar.
COMBINED = re.compile(r'combined(?:\s+length)?|including (?:the )?(?:tow|toad)|'
                      r'rv\s*\+\s*tow|total length|with (?:the )?tow vehicle|'
                      r'rig (?:and|plus) tow|overall length', re.I)
# Explicit confirmation that the toad can be left somewhere — worth surfacing,
# because it is the thing that makes a 40 ft site work.
TOAD_OK = re.compile(r'overflow|extra parking|additional parking|park(?:ing)? (?:the )?(?:toad|tow)'
                     r'|toad can be parked|separate parking|second vehicle', re.I)


def verdict(ft, some, combined):
    """Arithmetic only. 'some' means the figure came from a range, a tier or an
    explicit "a few sites", so it describes the best site rather than every one.
    That cuts both ways, and getting it wrong in the short direction is the
    expensive mistake: "some 30-amp spots fit only rigs ≤20 ft" at a park that
    advertises itself as big-rig friendly is not a 20 ft campground, and
    reporting it as one would strike a perfectly good stop off the list."""
    bar = COMBO_FT if combined else COACH_FT
    if combined:
        # Here the posted figure has to swallow the whole 60 ft.
        if ft >= COMBO_FT:
            v, label = 'fits', f'fits the coach and the toad together — the {ft} ft limit is a combined one'
        elif ft >= COACH_FT:
            return 'combined-tight', (f'{ft} ft is a COMBINED limit covering the tow vehicle, '
                                      f'so the coach alone fits but the 4x4 cannot stay on the site')
        else:
            v, label = 'too-short', 'shorter than the coach'
    elif ft >= COACH_FT + 5:
        v, label = 'fits', 'comfortable for the coach'
    elif ft >= COACH_FT:
        margin = ft - COACH_FT
        v = 'fits-exact'
        label = ('exactly the coach’s length — ask for a full-length site' if margin == 0
                 else f'fits with {margin} ft to spare — ask for a full-length site')
    elif some:
        return 'some-short', 'some sites are too short — book a long one'
    else:
        v, label = 'too-short', 'shorter than the coach'
    if some and v in ('fits', 'fits-exact'):
        label += ', but only some sites'
    return v, label


def analyse(o):
    t = o.get('rig_note') or ''
    if not t:
        return None
    clean = OURS.sub(' ‹rig› ', t)
    posted = hits(POSTED, clean)
    reported = hits(REPORTED, clean)

    if posted:
        lo, ft = min(posted), max(posted)
        some = bool(SOME.search(clean))
        spread = len(posted) > 1 and ft - lo > 10
        # A spread is only a conflict when the SHORT end could bite. "Max rig 65
        # ft, pull-throughs to 120 ft" is two true facts about two site types,
        # not a disagreement — if even the short end clears the combination
        # there is nothing to call about.
        if lo >= COMBO_FT:
            spread = False
        if spread and some:
            return {'s': 'some-short', 'ft': ft, 'lo': lo, 'src': 'posted',
                    'label': f'site types run {lo}–{ft} ft — book the long one'}
        if spread:
            return {'s': 'conflict', 'ft': ft, 'lo': lo, 'src': 'posted',
                    'label': f'sources give {lo}–{ft} ft — call before booking'}
        if CONFLICT.search(t):
            return {'s': 'conflict', 'ft': ft, 'src': 'posted',
                    'label': f'{ft} ft posted, but the sources disagree — call'}
        if SAYS_NO.search(t) and ft < COACH_FT:
            return {'s': 'too-short', 'ft': ft, 'src': 'posted',
                    'label': f'shorter than the coach · posted {ft} ft'}
        combined = bool(COMBINED.search(t))
        v, label = verdict(ft, some, combined)
        rec = {'s': v, 'ft': ft, 'src': 'posted', 'label': f'{label} · posted {ft} ft'}
        if TOAD_OK.search(t):
            rec['toad'] = 'the research mentions somewhere to leave the tow vehicle'
        return rec
    at = ATLEAST.search(clean)
    if at:
        ft = int(at.group(1) or at.group(2))
        if ft >= COACH_FT:
            return {'s': 'fits', 'ft': ft, 'src': 'posted', 'atleast': True,
                    'label': f'the operator states it takes rigs of {ft} ft and over — no maximum published'}
    if reported:
        if CONFLICT.search(t):
            lo, hi = min(reported), max(reported)
            span = f'{lo}–{hi} ft' if hi > lo else f'{hi} ft'
            return {'s': 'conflict', 'ft': hi, 'lo': lo,
                    'label': f'reports conflict ({span}) — nothing posted, call'}
        ft = max(reported)
        # A crowdsourced sighting is not a limit. It can only ever be reassurance
        # that something that size got in — never grounds to reject a park.
        if ft >= COACH_FT:
            return {'s': 'seen', 'ft': ft, 'src': 'reported',
                    'label': f'no posted limit; a {ft} ft rig is reported to have fitted'}
        return {'s': 'unknown', 'ft': None, 'src': 'reported',
                'label': f'no posted limit; the largest rig anyone reported is {ft} ft — that is not a limit, call and ask'}
    if UNPUBLISHED.search(t):
        return {'s': 'unpublished', 'ft': None, 'label': 'length limit not published — call and ask'}
    return None


def main():
    h = SRC.read_text()
    stops = json.loads(ex(h, 'const STOPS =', '[', ']'))
    ext = json.loads(ex(h, 'const EXT_DATA ='))['STOPS']

    out, counts, n_opts = {}, {}, 0
    for s in stops + ext:
        cr = s.get('campResearch') or {}
        for o in cr.get('paid_options') or []:
            n_opts += 1
            r = analyse(o)
            if not r:
                counts['no claim'] = counts.get('no claim', 0) + 1
                continue
            out[s['id'] + '|' + (o.get('name') or '')] = r
            counts[r['s']] = counts.get(r['s'], 0) + 1

    if not out:
        sys.exit('!! no rig-fit verdicts extracted at all — the patterns have broken')

    payload = json.dumps({'opts': out, 'coach': COACH_FT, 'combo': COMBO_FT},
                         ensure_ascii=False, sort_keys=True)
    decl = re.compile(r'const RIGFIT = \{.*?\};\n', re.S)
    block = f'const RIGFIT = {payload};\n'
    if decl.search(h):
        h = decl.sub(lambda _m: block, h, count=1)
    else:
        anchor = 'const PHOTO ='
        assert anchor in h, 'PHOTO declaration missing'
        h = h.replace(anchor, block + '\n' + anchor, 1)
    SRC.write_text(h)

    print(f"  {len(out)} of {n_opts} paid options carry a usable length claim")
    order = ['fits', 'fits-exact', 'combined-tight', 'some-short', 'too-short',
             'conflict', 'seen', 'unknown', 'unpublished', 'no claim']
    for k in order:
        if counts.get(k):
            print(f"     {k:<12}{counts[k]:>4}")
    print("wrote", SRC)


if __name__ == '__main__':
    main()

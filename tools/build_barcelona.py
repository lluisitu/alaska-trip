#!/usr/bin/env python3
"""
Inject the Barcelona trip mode into desktop/index.html.

    cd tools && python3 build_barcelona.py

Why a build script rather than a hand-edit
------------------------------------------
Same reason as every other trip here: `desktop/index.html` is the master but the
DATA inside it is generated, so a const edited by hand is silently overwritten by
the next build. The research lives in `barcelona_db.json` and this writes
`const BARCELONA` and `const BCN_DATA` from it.

What is different about this trip, and what must NOT be inherited
-----------------------------------------------------------------
There is no motorhome, no towed truck, no dog and no cat. The 40 ft rule, the
bike-carrier gravel question and the 30-minute radius from STOP_SPEC all belong
to Alaska and do not apply. LLuis set the radius himself: all of Catalonia.

So two of the card's boxes are deliberately empty — `offroad` and `cruise`. They
are not omitted by accident and they are not "not researched": there is no 4x4
and no dog, so the questions do not exist. The boxes that carry this trip are
`activities` (each day trip, with its day constraint in `when`), `alltrails`
(the specific walk) and `scenicDrives` (the drive out, with time from base).

The one rule that shapes everything: LLuis travels with his mother and family,
about 4 km is the comfortable walk, and surface matters more than distance. Every
walk on the card is chosen against that, and `family` carries the verdict.

Idempotent: md5 must be identical across three consecutive runs.
"""
import json, pathlib, re, sys
from urllib.parse import quote

HERE = pathlib.Path(__file__).resolve().parent
SRC  = HERE.parent / 'desktop' / 'index.html'
DB   = HERE / 'barcelona_db.json'

DATA_START = '/* barcelona data start — build_barcelona.py */'
DATA_END   = '/* barcelona data end — build_barcelona.py */'
VIEW_START = '<!-- barcelona views start — build_barcelona.py -->'
VIEW_END   = '<!-- barcelona views end — build_barcelona.py -->'

DOT = ' · '

BCN_STATS = """function bcnStatsHTML(){
  var b = BCN_DATA, s = b.stop, n = function(a){ return (a||[]).length; };
  var locked = (b.destinations||[]).filter(function(d){ return d.tier !== 'free'; }).length;
  var easy   = (b.destinations||[]).filter(function(d){ return d.family === 'all'; }).length;
  return [[s.nights,'nights'],[n(b.destinations),'day trips'],[locked,'tied to a day'],
          [easy,'work for everyone'],[n(s.alltrails),'walks'],[n(b.photo),'shots'],
          [n(b.issues),'gaps recorded']]
    .map(function(p){ return '<div class="stat"><b>'+p[0]+'</b><span>'+p[1]+'</span></div>'; }).join('');
}
"""


def esc(x):
    return (str('' if x is None else x)
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def joined(*bits):
    return DOT.join([b for b in bits if b])


def links_html(arr):
    return DOT.join('<a href="%s" target="_blank" rel="noopener">%s</a>'
                    % (l['url'], l.get('label') or 'source') for l in arr or [])


FAM = {'all':  'Works for everyone',
       'care': 'Works, with one thing to skip',
       'no':   'NOT for the group'}

TIER = {'date':    'LOCKED TO A DATE',
        'weekday': 'LOCKED TO A DAY OF THE WEEK',
        'free':    'Go whenever'}


def drive_label(d):
    m = d.get('drive_min')
    if not m:
        return 'in Barcelona'
    return '%dh%02d from Barcelona / %d km' % (m // 60, m % 60, d['drive_km']) if m >= 60 \
        else '%d min from Barcelona / %d km' % (m, d['drive_km'])


def shape(db):
    """Everything both builds need, in one dict.

    `stop` is deliberately a STOPS-shaped entry so the dashboard's own
    renderCards() draws it. Writing a second renderer is what made the first
    Cloudcroft card look nothing like an Alaska stop.
    """
    st = db['stop']
    dests = db.get('destinations') or []
    ordered = sorted(dests, key=lambda d: ({'date': 0, 'weekday': 1, 'free': 2}[d['tier']],
                                           d.get('drive_min') or 0))

    # The note leads the card, because the two Mondays and the three locked
    # dates govern every other choice on it.
    note = ('THE CALENDAR IS THE CONSTRAINT, not the distance. Three trips are tied to a date '
            '(La Mercè 26–27 Sep only; Empúries on 30 Sep if you want golden light inside the '
            'ruins; Sitges 8–10 Oct), three more to a day of the week, and BOTH MONDAYS — '
            '28 Sep and 5 Oct — are dead: Vallbona, Ullastret, Cardona, Pinell de Brai and '
            'Sant Pere de Rodes all close, and so does Mesón del Conde at Sant Martí. '
            'The rest float.')

    # One walk per day trip that has one. Distance and surface both, because
    # with a mixed-age group the surface is what decides it and 4 km of paved
    # promenade is a different thing from 4 km of roots and loose stone.
    trails = []
    for d in ordered:
        if not d.get('walk'):
            continue
        trails.append({'name': d['name'], 'url': (d.get('links') or [{}])[0].get('url') or '',
                       'difficulty': FAM.get(d['family']),
                       'distance': None, 'time': drive_label(d),
                       'note': joined(d['walk'], d.get('family_why'))})

    # Each day trip is an `activity`, because `when` is the dashboard's own
    # opening-hours-and-timing field and the day constraint is exactly that.
    activities = [{'name': d['name'],
                   'when': joined(TIER[d['tier']], d.get('when')),
                   'detail': joined(d['what'], ('FOOD: ' + d['food']) if d.get('food') else ''),
                   'links': d.get('links') or []}
                  for d in ordered]

    drives = [{'name': d['name'], 'url': (d.get('links') or [{}])[0].get('url') or None,
               'rig': 'car', 'distance': ('%d km' % d['drive_km']) if d.get('drive_km') else None,
               'note': joined(drive_label(d), FAM.get(d['family']), d.get('family_why'))}
              for d in ordered if d.get('drive_min')]

    stop = {
        'id': st['id'], 'name': st['name'], 'leg': 'barcelona',
        'lat': st['lat'], 'lng': st['lng'], 'nights': st['nights'],
        'arrive': st['arrive'], 'depart': st['depart'],
        'blurb': st['blurb'], 'note': note,
        'alltrails': trails,
        # Deliberately empty: no 4x4 and no dog on this trip, so neither
        # question exists. Empty is the correct answer, not a missing one.
        'offroad': [], 'cruise': [],
        'scenicDrives': drives,
        'activities': activities,
        'nearbyTowns': [
            {'name': 'Barcelona–El Prat (BCN)', 'distance': 'UA769 in 26 Sep 13:15 · UA770 out 11 Oct 15:15',
             'note': 'Arrival is a half day. Departure gives a morning only — airport by about 12:30.'},
            {'name': 'The car', 'distance': 'Hired for the whole stay',
             'note': 'Every drive time on this card was routed from Plaça de Catalunya with no traffic '
                     'modelled, so each is a floor rather than a promise.'}],
        'poi': [{'name': d['name'], 'lat': d['lat'], 'lng': d['lng'],
                 'type': 'sight' if d['tier'] != 'free' else 'trail'}
                for d in ordered if d.get('lat') and d.get('drive_min')],
        'weather': {'flag': 'green',
                    'reason': 'Late Sep about 26°C max / 17°C min, early Oct about 23°C / 16°C. '
                              'Sea around 24°C falling to 22°C — swimming is on for the whole '
                              'fortnight. Calçots are NOT in season; bolets are just starting.'},
        'tempF': {'avgMax': 77, 'avgMin': 62},
        'tz': st.get('tz'),
        'camp': 'Staying with family in Barcelona — nothing to book, and no rig constraint anywhere '
                'on this trip.',
        'campNotes': ['No motorhome, no towed truck, no pets. The 40 ft rule, the bike-carrier gravel '
                      'question and the 30-minute radius are Alaska rules and do not apply here.',
                      'LLuis set the radius himself: all of Catalonia, same-day return, with one or '
                      'two nights out allowed.'],
        'campResearch': {
            'verdict': 'No accommodation research needed — he is staying with family.',
            'paid_options': [], 'boondock_options': [],
            'caveats': ['The only overnight candidate left is Mont-rebei, and it is unresolved.']},
        'planNote': ' '.join('%s — %s.' % (d['name'], TIER[d['tier']]) for d in ordered),
    }

    photo = [{'title': s['title'], 'subject': s.get('subject'), 'vantage': s.get('vantage'),
              'light': s.get('light'), 'craft': s.get('craft')}
             for s in db.get('shots') or []]

    # green only where it is open and unconstrained. Anything with a recorded
    # gap is orange — an authority that publishes nothing is never green,
    # because no prohibition is not permission.
    highlights = []
    for d in ordered:
        if d['family'] == 'no':
            flag, reason = 'red', d['family_why']
        elif d.get('gaps'):
            flag, reason = 'orange', d['gaps'][0]
        elif d['tier'] != 'free':
            flag, reason = 'orange', d.get('when') or TIER[d['tier']]
        else:
            flag, reason = 'green', d.get('when') or 'No date constraint and nothing unresolved.'
        highlights.append({
            'stop_id': st['id'], 'stop_name': st['name'], 'name': d['name'],
            'type': 'sight', 'summary': d['what'],
            'link': (d.get('links') or [{}])[0].get('url')
                    or 'https://duckduckgo.com/?q=' + quote(d['name'] + ' Catalunya'),
            'flag': flag, 'flag_reason': reason})

    issues, n = [], 0

    def add(cat, sev, issue, analysis, solution=''):
        nonlocal n
        n += 1
        issues.append({'id': 'bcn-%d' % n, 'category': cat, 'severity': sev,
                       'stop_id': st['id'], 'stop_name': st['name'],
                       'issue': issue, 'analysis': analysis, 'solution': solution})

    for d in ordered:
        for g in d.get('gaps') or []:
            add('research', 'orange', d['name'] + ' — ' + g,
                'Recorded absent rather than guessed. An absence gets phoned about; a wrong '
                'number gets acted on.')
    for g in db.get('research_gaps') or []:
        add('research', 'orange', g, '')
    for u in db.get('unknowns') or []:
        add('research', 'orange', u, '')
    for c in db.get('calls') or []:
        add('logistics', 'orange', 'Call: ' + (c.get('who') or ''), c.get('ask') or '',
            ('☎ ' + c['number']) if c.get('number') else 'No number sourced yet.')

    # Overview: the blurb, the calendar rule, and the three tiers — built with
    # the page's own classes so it matches the other trips without a stylesheet.
    # NOT .subhead — that class uppercases, and the blurb is three sentences.
    # Rendered as caps it was a wall nobody would read.
    ov = ('<p style="font-size:.92rem;color:var(--muted);line-height:1.6;margin:0 0 12px 2px;'
          'max-width:78ch">%s</p>' % esc(st['blurb']))
    ov += ('<div class="rollup-wrap" style="border-left:3px solid #e0384d;margin-bottom:14px">'
           '<p class="subhead" style="margin:0 0 6px">The calendar is the constraint, not the '
           'distance</p><p style="font-size:.85rem;color:var(--muted);margin:0;line-height:1.55">'
           '%s</p></div>' % esc(note))
    rows = ''.join(
        '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
        % (esc(TIER[d['tier']]), esc(d['name']), esc(drive_label(d)),
           esc(joined(FAM.get(d['family']), d.get('when'))))
        for d in ordered)
    ov += ('<p class="subhead" style="margin:14px 2px 6px">Which trips are tied to a day</p>'
           '<p style="font-size:.78rem;color:var(--muted);margin:0 2px 8px">He is not doing all '
           'of them, so this is not an itinerary — it is which ones can float and which cannot.</p>'
           '<div class="timeline-wrap"><table class="tl" id="bcnTimelineTable">'
           '<tr><th>When</th><th>Where</th><th>Drive</th><th>What decides it</th></tr>%s'
           '</table></div>' % rows)

    return {'stop': stop, 'photo': photo, 'light': db.get('light_stop') or {},
            'highlights': highlights, 'issues': issues, 'overviewHTML': ov,
            'destinations': [{'id': d['id'], 'name': d['name'], 'tier': d['tier'],
                              'family': d['family'], 'drive_min': d.get('drive_min')}
                             for d in ordered],
            'legColor': '#d98a3c', 'legName': 'Barcelona & Catalonia'}


RENDER_JS = r"""
<script>
(function(){
  if (typeof BCN_DATA === 'undefined') return;
  window.BCN_STOP = BCN_DATA.stop;
  window.BCN_HIGHLIGHTS_BY_LEG = { barcelona: BCN_DATA.highlights };
  window.BCN_ISSUES = BCN_DATA.issues;
  if(typeof PHOTO !== 'undefined')      PHOTO[BCN_DATA.stop.id] = BCN_DATA.photo;
  if(typeof LIGHT !== 'undefined')      LIGHT[BCN_DATA.stop.id] = BCN_DATA.light;
  if(typeof LEG_COLORS !== 'undefined') LEG_COLORS.barcelona   = BCN_DATA.legColor;
  if(typeof LEG_NAMES !== 'undefined')  LEG_NAMES.barcelona    = BCN_DATA.legName;

  window.renderBarcelona = function(){
    if(typeof renderCards !== 'function') return;
    renderCards('all', [window.BCN_STOP], 'bcnCardsWrap');
    var o = document.getElementById('bcnOverviewWrap');
    if(o) o.innerHTML = BCN_DATA.overviewHTML;
    if(typeof renderHighlights === 'function')
      renderHighlights(window.BCN_HIGHLIGHTS_BY_LEG, 'bcnHighlightsWrap', 'bcnHlFilterBar');
    if(typeof renderIssues === 'function')
      renderIssues(window.BCN_ISSUES, 'bcnIssuesWrap', 'bcn');
    stripOffroadBox();
  };

  // There is no 4x4 and no dog on this trip, so the card's Offroad box is not an
  // unanswered question — the question does not exist. It is removed HERE rather
  // than made conditional in the shared renderer, because eleven Alaska stops
  // have an empty offroad box on purpose and its "search for 4x4 trails near
  // here" link is the right research prompt for them. An empty box on this card
  // would read as "nobody checked", which is the one thing it must not say.
  function stripOffroadBox(){
    var wrap = document.getElementById('bcnCardsWrap');
    if(!wrap) return;
    wrap.querySelectorAll('.g4-offroad').forEach(function(t){
      var box = t.closest('.grid4-box');
      if(box) box.remove();
    });
  }
  // The card body is built when the card is expanded, not when it is rendered,
  // so a one-shot strip runs before the box exists. Watch instead.
  var mo = new MutationObserver(stripOffroadBox);
  var startWatching = function(){
    var wrap = document.getElementById('bcnCardsWrap');
    if(wrap){ mo.observe(wrap, {childList:true, subtree:true}); stripOffroadBox(); }
  };

  // A one-base trip opens its only card, for the same reason Cloudcroft does:
  // collapsed, All Stops is a single header strip above an empty page, which
  // reads as broken rather than as "click me". It must not open while hidden —
  // initMiniMap() runs once and a Leaflet map built in a display:none container
  // sizes itself to zero and stays blank for good.
  var autoOpen = function(){
    var el = document.getElementById('card-' + BCN_DATA.stop.id);
    if(!el || el.classList.contains('open') || el.offsetParent === null) return false;
    if(typeof toggleCard !== 'function') return false;
    toggleCard(BCN_DATA.stop.id);
    return true;
  };
  var watch = function(){ setTimeout(function(){
    if(autoOpen()) document.removeEventListener('click', watch, true); }, 0); };
  document.addEventListener('click', watch, true);
  if(document.readyState !== 'loading') setTimeout(function(){ window.renderBarcelona(); startWatching(); }, 0);
  else document.addEventListener('DOMContentLoaded', function(){ window.renderBarcelona(); startWatching(); });
})();
</script>
"""


def replace_between(h, start, end, block, anchor, before=False):
    """Remove EVERY existing copy of the marked block, then insert one.

    Replacing only the first start..end pair is not the same thing: a run that
    inserted a second copy left the file growing by one block per build and
    never converging.
    """
    h = re.sub(r'\n*' + re.escape(start) + r'.*?' + re.escape(end) + r'\n*', '\n',
               h, flags=re.S)
    k = h.index(anchor)
    if not before:
        k += len(anchor)
    return h[:k] + '\n' + block + '\n' + h[k:]


def main():
    db = json.loads(DB.read_text())
    h = SRC.read_text()

    # A plain const, deliberately. build_mobile.py reads consts out of the built
    # desktop file; anything computed at page-load time is invisible to it, and
    # the trip ends up on the desktop and silently not on the phone.
    data = (DATA_START + '\nconst BARCELONA = '
            + json.dumps(db, ensure_ascii=False, separators=(',', ':')) + ';\n'
            + 'const BCN_DATA = '
            + json.dumps(shape(db), ensure_ascii=False, separators=(',', ':')) + ';\n'
            + BCN_STATS + DATA_END)
    h = replace_between(h, DATA_START, DATA_END, data, 'const TRIP_MODES = {', before=True)

    # One container per view. Spliced by OFFSET, not by anchoring on
    # '</section>' — that string is every section in the file, and using it put
    # all four blocks inside the first one.
    CONTAINERS = [
        ('card',       'view-stops',      '<div class="cards" id="bcnCardsWrap"></div>'),
        ('overview',   'view-overview',   '<div id="bcnOverviewWrap"></div>'),
        ('highlights', 'view-highlights', '<div id="bcnHighlightsWrap"></div>'),
        ('issues',     'view-issues',     '<div id="bcnIssuesWrap"></div>'),
    ]
    for tag, view, inner in CONTAINERS:
        st = '<!-- barcelona %s start — build_barcelona.py -->' % tag
        en = '<!-- barcelona %s end — build_barcelona.py -->' % tag
        blk = st + '\n<div class="bcn-only hidden">' + inner + '</div>\n' + en
        h = re.sub(r'\n*' + re.escape(st) + r'.*?' + re.escape(en) + r'\n*', '\n', h, flags=re.S)
        a = h.index('id="%s">' % view)
        b = h.index('</section>', a)
        h = h[:b] + blk + '\n' + h[b:]

    h = replace_between(h, VIEW_START, VIEW_END, VIEW_START + RENDER_JS + VIEW_END,
                        '</body>', before=True)

    bad = [i for i, ch in enumerate(h) if 0xD800 <= ord(ch) <= 0xDFFF]
    if bad:
        k = bad[0]
        sys.exit('!! build_barcelona: unpaired surrogate at offset %d - %r'
                 % (k, h[max(0, k - 70):k + 10]))

    tmp = SRC.with_suffix('.html.tmp')
    tmp.write_text(h, encoding='utf-8')
    tmp.replace(SRC)
    s = shape(db)
    print('build_barcelona: stop shaped for renderCards; %d day trips (%d tied to a day), '
          '%d walks, %d highlights, %d issues, %d shots'
          % (len(db.get('destinations') or []),
             sum(1 for d in s['destinations'] if d['tier'] != 'free'),
             len(s['stop']['alltrails']), len(s['highlights']), len(s['issues']),
             len(s['photo'])))


if __name__ == '__main__':
    main()

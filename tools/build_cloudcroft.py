#!/usr/bin/env python3
"""
Inject the Cloudcroft one-stop trip mode into desktop/index.html.

    cd tools && python3 build_cloudcroft.py

Why a build script rather than a hand-edit
------------------------------------------
`desktop/index.html` is the master, but the DATA inside it is generated — edit a
const by hand and the next build silently overwrites it. So Cloudcroft's
research lives in `cloudcroft_db.json` and this writes `const CLOUDCROFT` and
the `.cc-only` view blocks from it.

Everything is written between explicit start/end marker comments and replaced
whole, which is the convention this repo settled on after a regex that matched a
block's *shape* terminated at the first blank line, left half the old copy and
appended a second.

What is NOT generated: the toggle button, the TRIP_MODES entry and the
`setTripMode` visibility map. Those are page structure and live in the HTML
directly, each behind its own marker comment.

Idempotent: md5 must be identical across three consecutive runs.
"""
import json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent / 'desktop' / 'index.html'
DB = HERE / 'cloudcroft_db.json'

CSS_START = '/* cloudcroft css start — build_cloudcroft.py */'
CSS_END = '/* cloudcroft css end — build_cloudcroft.py */'
DATA_START = '/* cloudcroft data start — build_cloudcroft.py */'
DATA_END = '/* cloudcroft data end — build_cloudcroft.py */'
VIEW_START = '<!-- cloudcroft views start — build_cloudcroft.py -->'
VIEW_END = '<!-- cloudcroft views end — build_cloudcroft.py -->'



CC_STATS = """function ccStatsHTML(){
  var c = CLOUDCROFT, s = c.stop, n = function(a){ return (a||[]).length; };
  var cruiseOk = (c.cruise||[]).filter(function(x){ return /^\\s*works/i.test(x.verdict||''); }).length;
  var gaps = (c.trails||[]).reduce(function(t,x){ return t + ((x.needs||[]).length); }, 0);
  return [[s.nights,'nights'],[s.elevation_ft.toLocaleString(),'feet'],[n(c.trails),'trails'],
          [cruiseOk,'gravel rides'],[n(c.offroad),'4x4 routes'],[n(c.shots),'shots'],
          [gaps,'gaps recorded']]
    .map(function(p){ return '<div class="stat"><b>'+p[0]+'</b><span>'+p[1]+'</span></div>'; }).join('');
}
"""

# --------------------------------------------------------------------------
# The shaping lives in PYTHON, not in the page.
#
# It used to be built in JavaScript inside the injected block, which meant the
# phone build could not see it — build_mobile.py reads consts out of the built
# desktop file, and a value computed at page-load time is not a const. The tab
# existed on the desktop and simply was not on the phone, which is the failure
# this repo has already shipped once. One shaping, two consumers.
# --------------------------------------------------------------------------

GRAVEL = '\U0001F6B2'          # 🚲
DOT = ' · '


def esc(x):
    return (str('' if x is None else x)
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def more_links(arr):
    """Second sources, as real anchors. `tag` is injected as raw HTML into a
    <span class="tag">, so a Komoot or Forest Service link can ride along inside
    it without inventing a box the other trips do not have."""
    out = []
    for l in arr or []:
        out.append('<a href="%s" target="_blank" rel="noopener">%s</a>%s'
                   % (l['url'], l.get('label') or 'source',
                      ' — ' + l['note'] if l.get('note') else ''))
    return DOT.join(out)


def hours_for(db, name):
    k = str(name or '').lower()
    for x in db.get('hours') or []:
        n = str(x.get('name') or '').lower()[:14]
        if n and (n in k or k[:14] in n):
            return x
    return {}


def joined(*bits):
    return DOT.join([b for b in bits if b])


def shape(db):
    """Everything both builds need, in one dict.

    `stop` is deliberately a STOPS-shaped entry: that is what makes the
    dashboard's own renderCards() able to draw it, and what made the card stop
    looking like a lookalike of itself.
    """
    st, m = db['stop'], db.get('monsoon') or {}

    # The monsoon rule leads the card, because on these dates it governs the
    # hour of every outdoor thing on it.
    note = ''
    if m.get('season'):
        note = ('LATE AUGUST IS PEAK MONSOON, and it sets the clock for every day here: 5.65 in '
                'of rain in August against 3.10 in September (WRCC 291931). NPS: “Finish '
                'hiking in the morning and be out of canyons or away from washes before the '
                'afternoon.” The gravel ride runs the Rio Peñasco, a confirmed '
                'flash-flood channel with NO stream gauge — NWS El Paso: “due to the '
                'lack of gauges on this stream, it is difficult to know where the flooding '
                'currently is occurring.” There is nothing to check before you set off. '
                'Ride it in the morning.')

    trails = []
    for t in db.get('trails') or []:
        o = {'name': t['name'], 'url': (t.get('alltrails') or {}).get('url') or '',
             'difficulty': t.get('difficulty'), 'time': t.get('time'),
             'distance': t.get('distance'), 'rating': t.get('reviews'),
             'uses': t.get('uses')}
        if t.get('dogs') is not None:
            o['dogs'] = t['dogs']
        if t.get('cruise') is True:
            o['cruise'] = True
        o['tag'] = joined(
            (t['elevation_gain'] + ' gain') if t.get('elevation_gain') else '',
            t.get('note'), t.get('season'),
            ('Not sourced: ' + ' | '.join(t['needs'])) if t.get('needs') else '',
            ('Also: ' + more_links(t['other_links'])) if t.get('other_links') else '')
        trails.append(o)

    # The link text names the SOURCE. Seven of these roads exist on no site
    # LLuis uses, and the card should say which is which at a glance rather than
    # showing twelve identical-looking links.
    offroad = [{'name': r['name'], 'url': r.get('url'),
                'label': r.get('label') or r.get('listing_type') or 'route listing',
                'rig': 'truck', 'distance': r.get('distance'),
                'difficulty': r.get('difficulty'),
                'tag': joined(r.get('vehicle_class'), r.get('note'), r.get('season'))}
               for r in db.get('offroad') or []]

    # Every cruise candidate is listed, ruled-out ones included. "Nothing here
    # works" reads identically to "nobody checked" unless the reasons are on the
    # card.
    for x in db.get('cruise') or []:
        ok = bool(re.match(r'\s*works', x.get('verdict') or '', re.I))
        offroad.append({
            'name': (GRAVEL + ' ' if ok else GRAVEL + '✗ ') + x['name'],
            'url': x.get('url'), 'label': x.get('label') or x.get('tier') or 'source',
            'rig': 'truck', 'cruise': ok, 'distance': x.get('length'),
            'tag': joined('GRAVEL RIDE with the dog in the carrier' if ok
                          else 'RULED OUT for the dog carrier',
                          x.get('surface'), x.get('bike_legal'), x.get('verdict'),
                          x.get('season'),
                          ('Also: ' + more_links(x['other_links'])) if x.get('other_links') else '')})

    drives = [{'name': d['name'], 'url': d.get('url'), 'rig': 'truck',
               'distance': d.get('distance'),
               'tag': joined(d.get('note'), d.get('season'))}
              for d in db.get('scenicDrives') or []]

    activities = []
    for x in db.get('highlights') or []:
        hr = hours_for(db, x['name'])
        when = hr.get('when') or ''
        if str(hr.get('open_in_late_september') or '').lower().startswith('no'):
            when = 'CLOSED on these dates. ' + when
        activities.append({'name': x['name'], 'when': when, 'detail': x.get('detail'),
                           'links': (x.get('links') or [])
                                    + ([{'label': 'hours', 'url': hr['url']}] if hr.get('url') else [])})

    camps = db.get('campgrounds') or []
    stop = {
        'id': st['id'], 'name': st['name'], 'leg': 'cloudcroft',
        'lat': st['lat'], 'lng': st['lng'], 'nights': st['nights'],
        'arrive': st['arrive'], 'depart': st['depart'],
        'blurb': st['blurb'], 'note': note,
        'alltrails': trails, 'offroad': offroad, 'scenicDrives': drives,
        'activities': activities,
        'nearbyTowns': [
            {'name': 'Alamogordo, NM', 'distance': '~35 min / 20 mi down US-82',
             'note': 'Full resupply, fuel and the desert floor 4,300 ft below. The climb up is '
                     'the hard part of the drive.'},
            {'name': 'Mayhill, NM', 'distance': '~25 min / 18 mi east on US-82',
             'note': 'The gentle approach from Artesia comes through here, and Camp Rio is on it.'}],
        'poi': [{'name': 'Mexican Canyon Trestle vista', 'lat': 32.9642532, 'lng': -105.7474681,
                 'type': 'sight'},
                {'name': 'Trestle Recreation Area', 'lat': 32.957241, 'lng': -105.748959,
                 'type': 'trail'},
                {'name': 'White Sands National Park', 'lat': 32.809869, 'lng': -106.264225,
                 'type': 'sight'}],
        'weather': {'flag': 'amber' if m.get('season') else 'green',
                    'reason': ('Peak monsoon. No day is safer than another — the mornings '
                               'are.') if m.get('season') else 'No known seasonal-access conflict.'},
        'tempF': {'avgMax': (db.get('tempF') or {}).get('avgMax'),
                  'avgMin': (db.get('tempF') or {}).get('avgMin')},
        'tz': st.get('tz'),
        'camp': (camps[0]['name'] + ' — no operator here publishes a maximum length, so '
                 'every option is a phone call before booking.') if camps else '',
        'campNotes': [x['name'] + ' — ' + joined(
                          ('max ' + x['max_length']) if x.get('max_length')
                          else 'NO published max length', x.get('hookups'), x.get('phone'))
                      + '. ' + (x.get('note') or '') for x in camps],
        'campResearch': {
            'verdict': 'Every operator silent on maximum length — all three are calls.',
            'paid_options': [{'name': x['name'], 'url': x.get('url'), 'note': x.get('note')}
                             for x in camps],
            'boondock_options': [], 'caveats': [db.get('elevation_note') or '']},
        'planNote': ' '.join('%s %s — %s. %s' % (d['dow'], d['date'][8:], d['shape'], d['detail'])
                             for d in (db.get('plan') or {}).get('days') or []),
    }

    # The shot list and the light box live INSIDE the card on every other trip —
    # photoBlock() and lightBlock() read them out of PHOTO[id] and LIGHT[id].
    photo = [{'title': s['title'], 'subject': s.get('subject'),
              'vantage': s['vantage'] + (
                  ' <a href="https://www.google.com/maps/search/?api=1&query=%s,%s" '
                  'target="_blank" rel="noopener">%s,%s</a>'
                  % (s['lat'], s['lng'], s['lat'], s['lng'])
                  if s.get('lat') and s.get('lng') else ''),
              'light': s.get('light'), 'craft': s.get('craft')}
             for s in db.get('shots') or []]

    # red is "likely blocked", orange is "check season". An operator that
    # publishes nothing is orange, never green — no prohibition is not permission.
    highlights = []
    for x in db.get('highlights') or []:
        hr = hours_for(db, x['name'])
        op = str(hr.get('open_in_late_september') or hr.get('open') or '').lower()
        flag = 'red' if op.startswith('no') else 'green' if op.startswith('yes') else 'orange'
        reason = ('Closed on these dates. ' + (hr.get('when') or '')) if flag == 'red' else \
                 ('No operator publishes hours for these dates'
                  + (' — phone ' + hr['phone'] if hr.get('phone') else '')
                  + '. ' + (hr.get('when') or '')) if flag == 'orange' else (hr.get('when') or '')
        highlights.append({
            'stop_id': st['id'], 'stop_name': st['name'], 'name': x['name'],
            'type': x.get('type') or 'sight', 'summary': x.get('detail') or '',
            'link': ((x.get('links') or [{}])[0].get('url') or hr.get('url')
                     or 'https://duckduckgo.com/?q=' + quote(x['name'] + ' Cloudcroft NM')),
            'flag': flag, 'flag_reason': reason})

    issues, n = [], 0
    def add(cat, sev, issue, analysis, solution=''):
        nonlocal n
        n += 1
        issues.append({'id': 'cc-%d' % n, 'category': cat, 'severity': sev,
                       'stop_id': st['id'], 'stop_name': st['name'],
                       'issue': issue, 'analysis': analysis, 'solution': solution})
    for t in db.get('trails') or []:
        for need in t.get('needs') or []:
            add('research', 'orange', t['name'] + ' — ' + need,
                'Recorded absent rather than guessed. The Forest Service publishes no figure for '
                'this, and the app is not an authority.')
    for u in db.get('aug_unknowns') or []:
        add('research', 'orange', u if isinstance(u, str) else u.get('item', ''),
            '' if isinstance(u, str) else (u.get('why') or u.get('note') or ''))
    for x in db.get('aug_calls') or []:
        add('camping', 'orange',
            'Call: ' + (x if isinstance(x, str) else (x.get('who') or x.get('number') or '')),
            '' if isinstance(x, str) else (x.get('question') or x.get('why') or ''),
            '' if isinstance(x, str) else '☎ ' + (x.get('number') or ''))

    # Overview: the blurb, the monsoon rule, and the week. Built with the page's
    # own classes — .subhead, .rollup-wrap, .timeline-wrap, table.tl — so it
    # matches the other two trips without a stylesheet of its own.
    ov = '<p class="subhead" style="margin:0 0 10px 2px">%s</p>' % esc(st['blurb'])
    if m.get('season'):
        ov += ('<div class="rollup-wrap" style="border-left:3px solid #e0384d;margin-bottom:14px">'
               '<p class="subhead" style="margin:0 0 6px">Late August is peak monsoon, and it sets '
               'the clock for every day here</p><p style="font-size:.85rem;color:var(--muted);'
               'margin:0;line-height:1.55">%s %s</p></div>'
               % (esc(m.get('daily_pattern')), esc(m.get('lightning'))))
    days = (db.get('plan') or {}).get('days') or []
    if days:
        ov += ('<p class="subhead" style="margin:14px 2px 6px">The week, day by day</p>'
               '<p style="font-size:.78rem;color:var(--muted);margin:0 2px 8px">%s</p>'
               '<div class="timeline-wrap"><table class="tl" id="ccTimelineTable">'
               '<tr><th>Day</th><th>Date</th><th>Shape of the day</th><th>Detail</th></tr>%s'
               '</table></div>'
               % (esc((db.get('plan') or {}).get('_why')),
                  ''.join('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                          % (esc(d['dow']), esc(d['date']), esc(d['shape']), esc(d['detail']))
                          for d in days)))

    return {'stop': stop, 'photo': photo, 'light': db.get('light') or {},
            'highlights': highlights, 'issues': issues, 'overviewHTML': ov,
            'legColor': '#7ec488', 'legName': 'Cloudcroft, NM'}


# The page-side block is now assignment only. Everything above decided the
# shape; this just hands it to the renderers the other two trips already use.
RENDER_JS = r"""
<script>
(function(){
  if (typeof CC_DATA === 'undefined') return;
  window.CC_STOP = CC_DATA.stop;
  window.CC_HIGHLIGHTS_BY_LEG = { cloudcroft: CC_DATA.highlights };
  window.CC_ISSUES = CC_DATA.issues;
  if(typeof PHOTO !== 'undefined')      PHOTO[CC_DATA.stop.id] = CC_DATA.photo;
  if(typeof LIGHT !== 'undefined')      LIGHT[CC_DATA.stop.id] = CC_DATA.light;
  if(typeof LEG_COLORS !== 'undefined') LEG_COLORS.cloudcroft  = CC_DATA.legColor;
  if(typeof LEG_NAMES !== 'undefined')  LEG_NAMES.cloudcroft   = CC_DATA.legName;

  window.renderCloudcroft = function(){
    if(typeof renderCards !== 'function') return;
    renderCards('all', [window.CC_STOP], 'ccCardsWrap');
    var o = document.getElementById('ccOverviewWrap');
    if(o) o.innerHTML = CC_DATA.overviewHTML;
    // The same two renderers the other trips use, pointed at this trip's data.
    // A lookalike was written first, and it is why the card did not match.
    if(typeof renderHighlights === 'function')
      renderHighlights(window.CC_HIGHLIGHTS_BY_LEG, 'ccHighlightsWrap', 'ccHlFilterBar');
    if(typeof renderIssues === 'function')
      renderIssues(window.CC_ISSUES, 'ccIssuesWrap', 'cc');
  };

  // A one-stop trip opens its only card. Collapsed, All Stops is a single
  // header strip above an empty page — which reads as broken, not as "click
  // me". The other trips have 99 and 58 cards, so a list of collapsed headers
  // is the whole point there; here there is nothing to choose between.
  //
  // It must not open while the view is hidden: initMiniMap() runs once, is
  // remembered as done, and a Leaflet map built in a display:none container
  // sizes itself to zero and stays blank for good. So this waits for the card
  // to actually be on screen, and unhooks itself the moment it fires.
  var autoOpen = function(){
    var el = document.getElementById('card-' + CC_DATA.stop.id);
    if(!el || el.classList.contains('open') || el.offsetParent === null) return false;
    if(typeof toggleCard !== 'function') return false;
    toggleCard(CC_DATA.stop.id);
    return true;
  };
  var watch = function(){ setTimeout(function(){
    if(autoOpen()) document.removeEventListener('click', watch, true); }, 0); };
  document.addEventListener('click', watch, true);
  if(document.readyState !== 'loading') setTimeout(window.renderCloudcroft, 0);
  else document.addEventListener('DOMContentLoaded', window.renderCloudcroft);
})();
</script>
"""

def replace_between(h, start, end, block, anchor, before=False):
    """Remove EVERY existing copy of the marked block, then insert one.

    Replacing only the first start..end pair is not the same thing: a run that
    inserted a second copy left the file growing by one block per build and never
    converging. The newlines around the block are consumed too — stripping the
    block alone left the separator behind and the file gained a blank line at
    each insertion point on every run.

    `before=True` inserts immediately BEFORE the anchor.
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

    # Strip the bespoke CSS the earlier version injected — the card now uses the
    # dashboard's own classes, so there is nothing left to style.
    h = re.sub(r'\n*' + re.escape(CSS_START) + r'.*?' + re.escape(CSS_END) + r'\n*', '\n',
               h, flags=re.S)

    # CC_DATA is a plain const, deliberately. build_mobile.py reads consts out
    # of the built desktop file; a value computed at page-load time is invisible
    # to it, which is why the tab existed on the desktop and not on the phone.
    data = (DATA_START + '\nconst CLOUDCROFT = '
            + json.dumps(db, ensure_ascii=False, separators=(',', ':')) + ';\n'
            + 'const CC_DATA = '
            + json.dumps(shape(db), ensure_ascii=False, separators=(',', ':')) + ';\n'
            + CC_STATS + DATA_END)
    h = replace_between(h, DATA_START, DATA_END, data, 'const TRIP_MODES = {', before=True)

    # One container per view, each holding the same element the other two trips
    # give their own renderer. Injected at the CLOSE of the section, so the main
    # trip's ids come first in the document: where an id is unavoidably shared,
    # the earlier one wins every lookup, and the main trip must be the one that
    # wins. (A second plan bar, injected first, broke undo exactly this way.)
    CONTAINERS = [
        ('card',       'view-stops',      '<div class="cards" id="ccCardsWrap"></div>'),
        ('overview',   'view-overview',   '<div id="ccOverviewWrap"></div>'),
        ('highlights', 'view-highlights', '<div id="ccHighlightsWrap"></div>'),
        ('issues',     'view-issues',     '<div id="ccIssuesWrap"></div>'),
    ]
    for tag, view, inner in CONTAINERS:
        st = '<!-- cloudcroft %s start — build_cloudcroft.py -->' % tag
        en = '<!-- cloudcroft %s end — build_cloudcroft.py -->' % tag
        blk = st + '\n<div class="cc-only hidden">' + inner + '</div>\n' + en
        # Spliced by offset, not by an anchor string. The obvious anchor — the
        # section's own closing tag — is '\n  </section>', which is every
        # section in the file; using it put all four blocks inside the first one.
        h = re.sub(r'\n*' + re.escape(st) + r'.*?' + re.escape(en) + r'\n*', '\n', h, flags=re.S)
        a = h.index('id="%s">' % view)
        b = h.index('</section>', a)
        h = h[:b] + blk + '\n' + h[b:]

    # Remove the bespoke per-view containers the earlier version injected.
    for cid in ('ccOverview', 'ccStops', 'ccHighlights', 'ccIssues'):
        a = '<!-- cloudcroft %s start — build_cloudcroft.py -->' % cid
        b = '<!-- cloudcroft %s end — build_cloudcroft.py -->' % cid
        h = re.sub(r'\n*' + re.escape(a) + r'.*?' + re.escape(b) + r'\n*', '\n', h, flags=re.S)

    h = replace_between(h, VIEW_START, VIEW_END, VIEW_START + RENDER_JS + VIEW_END,
                        '</body>', before=True)

    bad = [i for i, ch in enumerate(h) if 0xD800 <= ord(ch) <= 0xDFFF]
    if bad:
        k = bad[0]
        sys.exit('!! build_cloudcroft: unpaired surrogate at offset %d - %r' % (k, h[max(0, k-70):k+10]))

    tmp = SRC.with_suffix('.html.tmp')
    tmp.write_text(h, encoding='utf-8')
    tmp.replace(SRC)
    print('build_cloudcroft: stop shaped for renderCards; %d trails, %d offroad+gravel, %d drives, '
          '%d highlights, %d shots' % (len(db['trails']), len(db['offroad']) + len(db['cruise']),
                                       len(db['scenicDrives']), len(db['highlights']),
                                       len(db['shots'])))


if __name__ == '__main__':
    main()

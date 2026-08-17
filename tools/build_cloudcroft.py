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

RENDER_JS = r"""
<script>
(function(){
  if (typeof CLOUDCROFT === 'undefined') return;
  var c = CLOUDCROFT;

  // Shape the research as a STOPS entry so the dashboard's own renderCards()
  // draws it. The first version wrote a parallel renderer, which is why the card
  // looked nothing like an Alaska stop and why the shot list and light box ended
  // up in a different tab instead of inside the card where they belong.
  var hoursFor = function(name){
    var k = String(name||'').toLowerCase();
    return (c.hours||[]).filter(function(x){
      var n = String(x.name||'').toLowerCase().slice(0,14);
      return n && (k.indexOf(n)>=0 || n.indexOf(k.slice(0,14))>=0); })[0]; };

  var moreLinks = function(arr){
    return (arr||[]).map(function(l){
      return '<a href="'+l.url+'" target="_blank" rel="noopener">'+(l.label||'source')+'</a>'
           + (l.note ? ' — '+l.note : ''); }).join(' \u00b7 '); };

  var activities = (c.highlights||[]).map(function(x){
    var hr = hoursFor(x.name) || {};
    var when = hr.when || '';
    var open = String(hr.open_in_late_september||'').toLowerCase();
    if(open.indexOf('no')===0) when = 'CLOSED on these dates. ' + when;
    return { name:x.name, when:when, detail:x.detail,
             links:(x.links||[]).concat(hr.url?[{label:'hours',url:hr.url}]:[]) }; });

  // The monsoon rule leads the card, because on these dates it governs the hour
  // of every outdoor thing on it.
  var m = c.monsoon||{};
  var note = m.season
    ? ('LATE AUGUST IS PEAK MONSOON, and it sets the clock for every day here: 5.65 in of rain in '
       + 'August against 3.10 in September (WRCC 291931). NPS: \u201cFinish hiking in the morning and '
       + 'be out of canyons or away from washes before the afternoon.\u201d The gravel ride runs the '
       + 'Rio Pe\u00f1asco, a confirmed flash-flood channel with NO stream gauge \u2014 NWS El Paso: '
       + '\u201cdue to the lack of gauges on this stream, it is difficult to know where the flooding '
       + 'currently is occurring.\u201d There is nothing to check before you set off. Ride it in the '
       + 'morning.')
    : '';

  var planTxt = c.plan ? (c.plan.days||[]).map(function(d){
      return d.dow + ' ' + d.date.slice(8) + ' \u2014 ' + d.shape + '. ' + d.detail; }).join(' ') : '';

  window.CC_STOP = {
    id: c.stop.id, name: c.stop.name, leg: 'cloudcroft',
    lat: c.stop.lat, lng: c.stop.lng, nights: c.stop.nights,
    arrive: c.stop.arrive, depart: c.stop.depart,
    blurb: c.stop.blurb,
    note: note,
    alltrails: (c.trails||[]).map(function(t){
      var o = {name:t.name, url:(t.alltrails&&t.alltrails.url)||'',
               difficulty:t.difficulty, time:t.time, distance:t.distance,
               rating:t.reviews, uses:t.uses, tag:''};
      if(t.dogs!==undefined && t.dogs!==null) o.dogs = t.dogs;
      if(t.cruise===true) o.cruise = true;
      var bits=[];
      if(t.elevation_gain) bits.push(t.elevation_gain+' gain');
      if(t.note) bits.push(t.note);
      if(t.season) bits.push(t.season);
      if((t.needs||[]).length) bits.push('Not sourced: '+t.needs.join(' | '));
      if((t.other_links||[]).length) bits.push('Also: '+moreLinks(t.other_links));
      o.tag = bits.join(' \u00b7 ');
      return o; }),
    offroad: (c.offroad||[]).map(function(r){
      // The link text names the SOURCE. Seven of these roads exist on no site
      // LLuis uses, and the card should say which is which at a glance rather
      // than showing twelve identical-looking links.
      return {name:r.name, url:r.url, label:r.label||r.listing_type||'route listing',
              rig:'truck', distance:r.distance, difficulty:r.difficulty,
              tag:[r.vehicle_class, r.note, r.season].filter(Boolean).join(' \u00b7 ')}; })
      // Every cruise candidate is listed, ruled-out ones included. "Nothing here
      // works" is only a real answer if the reasons are on the card — a filtered
      // list looks identical to a list nobody checked.
      .concat((c.cruise||[]).map(function(x){
          var ok = /^\s*works/i.test(x.verdict||'');
          return {name:(ok?'\uD83D\uDEB2 ':'\uD83D\uDEB2\u2717 ')+x.name,
                  url:x.url, label:x.label||x.tier||'source',
                  rig:'truck', cruise:ok, distance:x.length,
                  tag:[ok ? 'GRAVEL RIDE with the dog in the carrier'
                          : 'RULED OUT for the dog carrier', x.surface, x.bike_legal,
                       x.verdict, x.season,
                       (x.other_links||[]).length ? 'Also: '+moreLinks(x.other_links) : ''
                      ].filter(Boolean).join(' \u00b7 ')}; })),
    scenicDrives: (c.scenicDrives||[]).map(function(d){
      return {name:d.name, url:d.url, rig:'truck', distance:d.distance,
              tag:[d.note, d.season].filter(Boolean).join(' \u00b7 ')}; }),
    activities: activities,
    nearbyTowns: [{name:'Alamogordo, NM', distance:'~35 min / 20 mi down US-82',
                   note:'Full resupply, fuel and the desert floor 4,300 ft below. The climb up is '
                        +'the hard part of the drive.'},
                  {name:'Mayhill, NM', distance:'~25 min / 18 mi east on US-82',
                   note:'The gentle approach from Artesia comes through here, and Camp Rio is on it.'}],
    poi: [{name:'Mexican Canyon Trestle vista', lat:32.9642532, lng:-105.7474681, type:'sight'},
          {name:'Trestle Recreation Area', lat:32.957241, lng:-105.748959, type:'trail'},
          {name:'White Sands National Park', lat:32.809869, lng:-106.264225, type:'sight'}],
    weather: {flag: m.season ? 'amber' : 'green',
              reason: m.season ? 'Peak monsoon. No day is safer than another \u2014 the mornings are.'
                               : 'No known seasonal-access conflict.'},
    tempF: {avgMax:(c.tempF||{}).avgMax, avgMin:(c.tempF||{}).avgMin},
    tz: c.stop.tz,
    camp: (c.campgrounds||[])[0] ? (c.campgrounds[0].name+' \u2014 no operator here publishes a '
          +'maximum length, so every option is a phone call before booking.') : '',
    campNotes: (c.campgrounds||[]).map(function(x){
      return x.name+' \u2014 '+[x.max_length?('max '+x.max_length):'NO published max length',
             x.hookups, x.phone].filter(Boolean).join(' \u00b7 ')+'. '+(x.note||''); }),
    campResearch: {verdict:'Every operator silent on maximum length \u2014 all three are calls.',
                   paid_options:(c.campgrounds||[]).map(function(x){
                     return {name:x.name, url:x.url, note:x.note}; }),
                   boondock_options:[], caveats:[c.elevation_note||'']},
    planNote: planTxt
  };

  // The shot list and the light box live INSIDE the card on every other trip,
  // and photoBlock()/lightBlock() read them out of PHOTO[id] and LIGHT[id].
  if(typeof PHOTO !== 'undefined') PHOTO[c.stop.id] = (c.shots||[]).map(function(s){
    return {title:s.title, subject:s.subject,
            vantage:s.vantage + ((s.lat&&s.lng)
              ? ' <a href="https://www.google.com/maps/search/?api=1&query='+s.lat+','+s.lng
                +'" target="_blank" rel="noopener">'+s.lat+','+s.lng+'</a>' : ''),
            light:s.light, craft:s.craft}; });
  if(typeof LIGHT !== 'undefined') LIGHT[c.stop.id] = c.light;
  if(typeof LEG_COLORS !== 'undefined') LEG_COLORS.cloudcroft = '#7ec488';
  if(typeof LEG_NAMES !== 'undefined') LEG_NAMES.cloudcroft = 'Cloudcroft, NM';

  var esc = function(x){ return String(x==null?'':x)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); };

  /* ---- Highlights: the dashboard's own rollup, one leg deep ------------- */
  window.CC_HIGHLIGHTS_BY_LEG = { cloudcroft: (c.highlights||[]).map(function(x){
    var hr = hoursFor(x.name) || {};
    var open = String(hr.open_in_late_september||hr.open||'').toLowerCase();
    // red is "likely blocked", orange is "check season". An operator that
    // publishes nothing is orange, never green — no prohibition is not permission.
    var flag = open.indexOf('no')===0 ? 'red' : open.indexOf('yes')===0 ? 'green' : 'orange';
    return { stop_id:c.stop.id, stop_name:c.stop.name, name:x.name,
             type:x.type||'sight', summary:x.detail||'',
             link:(x.links&&x.links[0]&&x.links[0].url) || hr.url
                  || 'https://duckduckgo.com/?q='+encodeURIComponent(x.name+' Cloudcroft NM'),
             flag:flag,
             flag_reason: flag==='red' ? ('Closed on these dates. '+(hr.when||''))
                        : flag==='orange' ? ('No operator publishes hours for these dates'
                                             + (hr.phone?' — phone '+hr.phone:'')+'. '+(hr.when||''))
                        : (hr.when||'') }; }) };

  /* ---- Known issues: every gap, as an issue card ------------------------ */
  var iss = [], nid = 0;
  var push = function(o){ o.id = 'cc-'+(++nid); o.stop_id = c.stop.id;
    o.stop_name = c.stop.name; iss.push(o); };
  (c.trails||[]).forEach(function(t){ (t.needs||[]).forEach(function(n){
    push({ category:'research', severity:'orange', issue:t.name+' — '+n,
           analysis:'Recorded absent rather than guessed. The Forest Service publishes no '
                  + 'figure for this and the app is not an authority.', solution:'' }); }); });
  (c.aug_unknowns||[]).forEach(function(u){
    push({ category:'research', severity:'orange',
           issue: typeof u==='string' ? u : (u.item||''),
           analysis: typeof u==='string' ? '' : (u.why||u.note||''), solution:'' }); });
  (c.aug_calls||[]).forEach(function(x){
    push({ category:'camping', severity:'orange',
           issue: 'Call: ' + (typeof x==='string' ? x : (x.who||x.number||'')),
           analysis: typeof x==='string' ? '' : (x.question||x.why||''),
           solution: typeof x==='string' ? '' : ('☎ '+(x.number||'')) }); });
  window.CC_ISSUES = iss;

  /* ---- Overview: the blurb, the monsoon rule, and the week -------------- */
  var ov = '<p class="subhead" style="margin:0 0 10px 2px">'+esc(c.stop.blurb)+'</p>';
  if(m.season){
    ov += '<div class="rollup-wrap" style="border-left:3px solid #e0384d;margin-bottom:14px">'
       + '<p class="subhead" style="margin:0 0 6px">Late August is peak monsoon, and it sets the '
       + 'clock for every day here</p><p style="font-size:.85rem;color:var(--muted);margin:0;'
       + 'line-height:1.55">'+esc(m.daily_pattern||'')+' '+esc(m.lightning||'')+'</p></div>';
  }
  if(c.plan && (c.plan.days||[]).length){
    ov += '<p class="subhead" style="margin:14px 2px 6px">The week, day by day</p>'
       + '<p style="font-size:.78rem;color:var(--muted);margin:0 2px 8px">'
       + esc(c.plan._why||'') + '</p>'
       + '<div class="timeline-wrap"><table class="tl" id="ccTimelineTable"><tr>'
       + '<th>Day</th><th>Date</th><th>Shape of the day</th><th>Detail</th></tr>'
       + c.plan.days.map(function(d){ return '<tr><td>'+esc(d.dow)+'</td><td>'
           + esc(d.date)+'</td><td>'+esc(d.shape)+'</td><td>'+esc(d.detail)
           + '</td></tr>'; }).join('') + '</table></div>';
  }

  window.renderCloudcroft = function(){
    if(typeof renderCards !== 'function') return;
    renderCards('all', [window.CC_STOP], 'ccCardsWrap');
    var o = document.getElementById('ccOverviewWrap');
    if(o) o.innerHTML = ov;
    // Same two renderers the other trips use, pointed at this trip's data. A
    // lookalike was written first, and it is why the card did not match.
    if(typeof renderHighlights === 'function')
      renderHighlights(window.CC_HIGHLIGHTS_BY_LEG, 'ccHighlightsWrap', 'ccHlFilterBar');
    if(typeof renderIssues === 'function')
      renderIssues(window.CC_ISSUES, 'ccIssuesWrap', 'cc');
  };
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

    data = (DATA_START + '\nconst CLOUDCROFT = '
            + json.dumps(db, ensure_ascii=False, separators=(',', ':')) + ';\n'
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

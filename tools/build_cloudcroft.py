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

# Layout classes the dashboard does not already define. Everything else reuses the
# page's own vocabulary — .pill, .pill-easy, .pill-dog-ok, .sec-head, .linklist.
CSS_RULES = """.cc-card{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:20px;margin:16px 0;}
.cc-blurb{margin:0 0 18px;color:var(--text);max-width:76ch;}
.cc-sec{margin:22px 0 0;}
.cc-sub{margin:-4px 0 10px;color:var(--muted);font-size:.86rem;max-width:74ch;}
.cc-card ul.linklist{list-style:none;margin:0;padding:0;}
.cc-card ul.linklist>li{padding:13px 0;border-top:1px solid var(--border);}
.cc-card ul.linklist>li:first-child{border-top:none;padding-top:2px;}
.cc-card .iname{font-weight:650;line-height:1.4;}
.cc-card .idet{margin-top:7px;font-size:.89rem;color:var(--muted);line-height:1.55;max-width:76ch;}
.cc-when{margin-top:7px;font-size:.89rem;color:var(--text);background:var(--panel2);border-radius:6px;padding:8px 10px;max-width:76ch;}
.cc-season{margin-top:7px;font-size:.86rem;color:var(--text);border-left:2px solid var(--accent);padding-left:10px;max-width:76ch;}
.cc-lk{margin-top:9px;font-size:.8rem;}
.cc-unk{border-style:dashed;}
.cc-truck{color:var(--accent2);border-color:rgba(95,180,214,.45);}
.cc-warn{background:rgba(230,163,74,.18);color:#e6a34a;border-color:rgba(230,163,74,.45);}
.cc-light{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;}
.cc-light>div{background:var(--panel2);border-radius:8px;padding:10px 12px;}
.cc-light span{display:block;font-size:.66rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);}
.cc-light b{display:block;font-size:1.1rem;font-variant-numeric:tabular-nums;margin-top:2px;}
.cc-light i{font-style:normal;font-size:.72rem;color:var(--muted);}
.cc-card details{margin-top:8px;}
.cc-card summary{cursor:pointer;font-size:.76rem;color:var(--muted);}
ul.cc-needs{margin:8px 0 0;padding-left:20px;font-size:.83rem;color:var(--muted);}
ul.cc-needs li{margin-bottom:5px;}
.cc-alert{background:var(--panel2);border:1px solid var(--border);border-left:3px solid #e0384d;border-radius:8px;padding:14px 16px;margin:0 0 16px;}
.cc-alert b{display:block;margin-bottom:6px;}
.cc-alert p{margin:0;font-size:.89rem;color:var(--muted);line-height:1.55;}"""


def replace_between(h, start, end, block, anchor, before=False):
    """Remove EVERY existing copy of the marked block, then insert one.

    The first version replaced only the first start..end pair, which is not the
    same thing: a run that inserted a second copy left the file growing by one
    block per build and never converged. Stripping all copies first is
    idempotent by construction and does not care how the duplicates got there.

    `before=True` inserts immediately BEFORE the anchor rather than after —
    needed for CSS, which has to land inside <style> and not after the closing
    tag, where it is inert text in the body.
    """
    # Consume the newlines around the old block too. Stripping the block alone
    # left the separator behind, so every run added one blank line at each of the
    # three insertion points and the md5 never settled — the file grew by three
    # lines a build while looking otherwise identical.
    h = re.sub(r'\n*' + re.escape(start) + r'.*?' + re.escape(end) + r'\n*', '\n',
               h, flags=re.S)
    k = h.index(anchor)
    if not before:
        k += len(anchor)
    return h[:k] + '\n' + block + '\n' + h[k:]


def main():
    db = json.loads(DB.read_text())
    h = SRC.read_text()

    # ---- css for the cc-only layout classes -------------------------------
    css = CSS_START + "\n" + CSS_RULES + "\n" + CSS_END
    h = replace_between(h, CSS_START, CSS_END, css, '</style>', before=True)

    # ---- the data const ---------------------------------------------------
    data = (DATA_START + '\nconst CLOUDCROFT = '
            + json.dumps(db, ensure_ascii=False, separators=(',', ':')) + ';\n'
            + '''function ccStatsHTML(){
  const c = CLOUDCROFT, s = c.stop;
  const n = (a)=> (a||[]).length;
  const cruiseOk = (c.cruise||[]).filter(x=>/^\\s*works/i.test(x.verdict||'')).length;
  const gaps = (c.trails||[]).reduce((t,x)=>t+((x.needs||[]).length),0);
  return [
    ['<b>'+s.nights+'</b>','nights'],
    ['<b>'+s.elevation_ft.toLocaleString()+'</b>','feet'],
    ['<b>'+n(c.trails)+'</b>','trails'],
    ['<b>'+cruiseOk+'</b>','gravel rides'],
    ['<b>'+n(c.offroad)+'</b>','4x4 routes'],
    ['<b>'+n(c.shots)+'</b>','shots'],
    ['<b>'+gaps+'</b>','gaps recorded'],
  ].map(([v,l])=>'<div class="stat">'+v+'<span>'+l+'</span></div>').join('');
}
'''
            + DATA_END)
    # BEFORE the declaration, not after: anchoring after it dropped
    # `const CLOUDCROFT = ...` inside the TRIP_MODES object literal, which is a
    # syntax error that takes the whole page down. It has to precede TRIP_MODES
    # anyway, since the cloudcroft entry reads ccStatsHTML.
    h = replace_between(h, DATA_START, DATA_END, data, 'const TRIP_MODES = {', before=True)

    # ---- the view blocks --------------------------------------------------
    # One .cc-only wrapper per view section, rendered client-side from CLOUDCROFT
    # so the markup here stays small and the data stays in one place.
    views = VIEW_START + '''
<div class="cc-only hidden" id="ccOverview"></div>
<script>
(function(){
  if (typeof CLOUDCROFT === 'undefined') return;
  const c = CLOUDCROFT, esc = (s)=>String(s==null?'':s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  const A = (u,t)=> u ? '<a href="'+esc(u)+'" target="_blank" rel="noopener">'+esc(t)+' \\u2197</a>' : '';
  const P = (t,k)=> '<span class="pill '+(k||'')+'">'+esc(t)+'</span>';
  const dcls = d=>{ d=(d||'').toLowerCase();
    return d.indexOf('easy')===0?'pill-easy':d.indexOf('moderate')===0?'pill-moderate':'pill-hard'; };
  const dogP = v=> v===true ? P('\\uD83D\\uDC15 dogs OK','pill-dog-ok')
                 : v===false ? P('\\uD83D\\uDEAB no dogs','pill-dog-no')
                 : P('dog rule unpublished','cc-unk');
  const needs = ns => (ns&&ns.length)
    ? '<details><summary>Not sourced ('+ns.length+')</summary><ul class="cc-needs">'
      + ns.map(n=>'<li>'+esc(n)+'</li>').join('') + '</ul></details>' : '';
  const row = (title,pills,body,links)=>
    '<li><div class="iname">'+title+'</div>'
    + (pills.length?'<div class="pills">'+pills.join('')+'</div>':'')
    + body + (links.filter(Boolean).length?'<div class="cc-lk">'+links.filter(Boolean).join(' \\u00b7 ')+'</div>':'')
    + '</li>';
  const sec = (icon,title,sub,inner)=>
    '<section class="cc-sec"><div class="sec-head">'+icon+' '+esc(title)+'</div>'
    + (sub?'<p class="cc-sub">'+esc(sub)+'</p>':'')
    + '<ul class="linklist">'+inner+'</ul></section>';

  const hoursFor = (name)=>{
    const k = String(name||'').toLowerCase();
    return (c.hours||[]).find(x=>{
      const n = String(x.name||'').toLowerCase();
      return n.slice(0,14) && (k.indexOf(n.slice(0,14))>=0 || n.indexOf(k.slice(0,14))>=0);
    });
  };

  const trails = (c.trails||[]).map(t=>{
    const ps = [];
    if(t.difficulty) ps.push(P(t.difficulty, dcls(t.difficulty)));
    if(t.time) ps.push(P('\\u23F1 '+t.time,'pill-distance'));
    if(t.distance) ps.push(P('\\uD83D\\uDCCF '+t.distance,'pill-distance'));
    if(t.elevation_gain) ps.push(P('\\u2191 '+t.elevation_gain,'pill-distance'));
    if(t.reviews) ps.push(P('\\u2605 '+t.reviews,'pill-rating'));
    ps.push(dogP(t.dogs));
    (t.uses||[]).forEach(u=>ps.push(P(u, /^(hike|bike|horse)$/.test(u)?('pill-'+u):'cc-unk')));
    if(t.cruise===false) ps.push(P('\\uD83D\\uDEB2 not a carrier route','cc-unk'));
    let b = t.note?'<div class="idet">'+esc(t.note)+'</div>':'';
    if(t.cruise_reason) b += '<div class="idet">'+esc(t.cruise_reason)+'</div>';
    if(t.season) b += '<div class="cc-season">'+esc(t.season)+'</div>';
    b += needs(t.needs);
    const lk = [(t.alltrails&&t.alltrails.url)?A(t.alltrails.url,'AllTrails'):''].concat(
      (t.other_links||[]).map(o=>A(o.url,o.label||'source')));
    return row(esc(t.name), ps, b, lk);
  }).join('');

  const routes = (arr)=> (arr||[]).map(r=>{
    const ps=[P('\\uD83D\\uDEFB truck','cc-truck')];
    if(r.vehicle_class) ps.push(P(String(r.vehicle_class).slice(0,64),'cc-unk'));
    if(r.distance) ps.push(P('\\uD83D\\uDCCF '+String(r.distance).slice(0,64),'pill-distance'));
    if(r.difficulty) ps.push(P(String(r.difficulty).slice(0,72),'pill-distance'));
    let b = r.note?'<div class="idet">'+esc(r.note)+'</div>':'';
    if(r.season) b += '<div class="cc-season">'+esc(r.season)+'</div>';
    return row(esc(r.name), ps, b, [A(r.url, r.listing_type||r.tier||'route listing')]);
  }).join('');

  const cruise = (c.cruise||[]).map(x=>{
    const ok = /^\\s*works/i.test(x.verdict||'');
    const ps=[P(ok?'\\uD83D\\uDEB2 gravel cruise':'\\uD83D\\uDEB2 ruled out', ok?'pill-cruise':'cc-unk')];
    ['length','surface','gradient'].forEach(k=>{ if(x[k]) ps.push(P(String(x[k]).slice(0,58),'pill-distance')); });
    if(x.bike_legal) ps.push(P('bike-legal: '+String(x.bike_legal).slice(0,46),'cc-unk'));
    let b = x.verdict?'<div class="idet">'+esc(x.verdict)+'</div>':'';
    if(x.season) b += '<div class="cc-season">'+esc(x.season)+'</div>';
    return row(esc(x.name), ps, b, [A(x.url, x.tier||'source')]);
  }).join('');

  const highlights = (c.highlights||[]).map(x=>{
    const hr = hoursFor(x.name), ps=[];
    if(hr){
      const o = String(hr.open_in_late_september||hr.open||'').toLowerCase();
      ps.push(o.indexOf('no')===0 ? P('closed on these dates','pill-dog-no')
            : o.indexOf('yes')===0 ? P('open on these dates','pill-dog-ok')
            : P('opening unknown','cc-unk'));
      if(hr.phone) ps.push(P('\\u260E '+hr.phone,'pill-rating'));
    }
    let b = x.detail?'<div class="idet">'+esc(x.detail)+'</div>':'';
    if(hr&&hr.when) b += '<div class="cc-when"><b>When \\u2014</b> '+esc(hr.when)+'</div>';
    if(hr&&hr.note) b += '<div class="idet">'+esc(hr.note)+'</div>';
    const lk = (x.links||[]).map(l=>A(l.url,l.label));
    if(hr&&hr.url) lk.push(A(hr.url,'hours'));
    return row(esc(x.name), ps, b, lk);
  }).join('');

  const shots = (c.shots||[]).map(s=>{
    const ps = (s.lat&&s.lng)
      ? ['<span class="pill pill-rating"><a href="https://www.google.com/maps/search/?api=1&query='
         +s.lat+','+s.lng+'" target="_blank" rel="noopener">\\uD83D\\uDCCD '+s.lat+', '+s.lng+'</a></span>']
      : [P('no published coordinate','cc-unk')];
    const b = (s.subject?'<div class="idet">'+esc(s.subject)+'</div>':'')
      + '<div class="cc-when"><b>Vantage \\u2014</b> '+esc(s.vantage)+'</div>'
      + '<div class="cc-season"><b>Light \\u2014</b> '+esc(s.light)+'</div>'
      + '<div class="idet"><b>Craft \\u2014</b> '+esc(s.craft)+'</div>'
      + needs(s.needs);
    return row(esc(s.title), ps, b, []);
  }).join('');

  const camps = (c.campgrounds||[]).map(x=>{
    const ps=[P(x.max_length? ('max '+x.max_length) : '\\u26A0 no published max length',
                x.max_length?'pill-distance':'cc-warn')];
    if(x.hookups) ps.push(P(String(x.hookups).slice(0,60),'pill-distance'));
    if(x.phone) ps.push(P('\\u260E '+x.phone,'pill-rating'));
    let b = x.note?'<div class="idet">'+esc(x.note)+'</div>':'';
    if(x.season) b += '<div class="cc-season">'+esc(x.season)+'</div>';
    return row(esc(x.name), ps, b, [A(x.url,'operator')]);
  }).join('');

  const L = c.light||{}, gm=L.goldenMorning||[], ge=L.goldenEvening||[];
  const cell=(l,v,i)=>'<div><span>'+esc(l)+'</span><b>'+esc(v)+'</b><i>'+esc(i)+'</i></div>';
  const light = '<section class="cc-sec"><div class="sec-head">\\uD83C\\uDF05 Light</div>'
    + '<div class="cc-light">'
    + cell('Sunrise', L.sunrise, (L.sunriseDir||'')+' '+(L.sunriseAz||'')+'\\u00b0')
    + cell('Sunset', L.sunset, (L.sunsetDir||'')+' '+(L.sunsetAz||'')+'\\u00b0')
    + cell('Golden \\u2014 morning', gm.join('\\u2013'), (L.goldenMinutes||'')+' min')
    + cell('Golden \\u2014 evening', ge.join('\\u2013'), (L.goldenMinutes||'')+' min')
    + cell('Day length', (L.dayLength||'')+' h', '')
    + cell('Astronomical dark', (L.darkStart||'')+'\\u2013'+(L.darkEnd||''), (L.darkHours||'')+' h')
    + cell('Moon on arrival', Math.round((L.moonFrac||0)*100)+'%', L.moonPhase||'')
    + cell('Darkest night', L.darkestNight, 'moon '+Math.round((L.darkestFrac||0)*100)+'%')
    + '</div><p class="idet" style="margin-top:10px">Computed by <code>build_light.py</code>, not '
    + 'researched. Two numbers organise the stop: the sun sets at '+esc(L.sunsetAz)+'\\u00b0, so the '
    + 'western rim \\u2014 which is everything worth photographing here \\u2014 is <b>frontlit in the '
    + 'morning and a silhouette in the evening</b>. And the moon is '
    + Math.round((L.moonFrac||0)*100)+'% on arrival and the darkest night is still '
    + Math.round((L.darkestFrac||0)*100)+'%, so <b>this is a moonlight week, not a Milky Way '
    + 'week</b> \\u2014 which is why the White Sands full-moon night on the 23rd is the '
    + 'night shot here, and the gypsum is the one subject in the region that is better '
    + 'under a full moon than under none.</p></section>';

  // The monsoon banner leads, because on these dates it governs the HOURS of every
  // outdoor thing below it — and the gravel ride runs a canyon with no stream gauge.
  const m = c.monsoon||{};
  const banner = !m.season ? '' : ('<div class="cc-alert"><b>Late August is the peak of the '
    + 'monsoon, and it sets the clock for every day of this stay</b>'
    + '<p>Cloudcroft\u2019s own record puts <b>5.65 in of rain in August against 3.10 in '
    + 'September</b> (WRCC 291931) \u2014 the dates sit on the wettest fortnight of the year, not '
    + 'the drying-out side of it. The rule every authority publishes is the same one. NPS: '
    + '<i>\u201cFinish hiking in the morning and be out of canyons or away from washes before the '
    + 'afternoon.\u201d</i> NWS Tucson adds <i>\u201cavoid being outside between mid afternoon and '
    + 'mid evening, especially in higher elevations.\u201d</i></p>'
    + '<p style="margin-top:8px">The gravel ride below runs the <b>Rio Pe\u00f1asco, a confirmed '
    + 'flash-flood channel with no stream gauge</b> \u2014 NWS El Paso: <i>\u201cdue to the lack of '
    + 'gauges on this stream, it is difficult to know where the flooding currently is '
    + 'occurring.\u201d</i> There is nothing to check before you set off. Ride it in the morning.</p>'
    + '</div>');

  document.getElementById('ccOverview').innerHTML =
      '<div class="cc-card">'
    + '<p class="cc-blurb">'+esc(c.stop.blurb)+'</p>'
    + banner
    + (function(){
        const pl = c.plan; if(!pl) return '';
        return '<section class="cc-sec"><div class="sec-head">📅 The week, day by day</div>'
          + '<p class="cc-sub">'+esc(pl._why)+'</p><ul class="linklist">'
          + (pl.days||[]).map(function(d){
              return '<li><div class="iname">'+esc(d.dow)+' '+esc(d.date.slice(8))+' \u2014 '
                + esc(d.shape)+'</div><div class="idet">'+esc(d.detail)+'</div></li>';
            }).join('')
          + '</ul></section>';
      })()
    + sec('\\uD83E\\uDD7E','Itinerary and highlights','Each carries its opening window where an operator publishes one \\u2014 and says so where none does.', highlights)
    + sec('\\u26F0\\uFE0F','Trails','About one walk per night, easy and moderate leading. Permitted uses come from the Forest Service trails table, not from the app.', trails)
    + sec('\\uD83D\\uDC15','The dog','', '<li><div class="iname">Lincoln National Forest publishes no dog rule at all</div>'
        + '<div class="idet">Seven of the eight trails above therefore carry no dog verdict \\u2014 an absence of '
        + 'prohibition is not permission, and the two must never look the same at a trailhead. What binds is '
        + '<b>36 CFR 261.16(j)</b>: a six-foot leash, but only at developed recreation sites, not on the tread.</div>'
        + '<div class="cc-season">'+esc((c.dogs||{}).rule)+'</div>'
        + '<div class="cc-lk">'+A((c.dogs||{}).source,'36 CFR 261.16')+'</div></li>'
        + '<li><div class="iname">In the village and at White Sands</div><div class="idet">'
        + esc((c.dogs||{}).notes)+'</div></li>')
    + sec('\\uD83D\\uDEB2','Gravel and the bike carrier','The dog rides in a carrier, so the question is a firm, flat, bike-legal surface \\u2014 not whether there is mountain biking.', cruise)
    + sec('\\uD83D\\uDEFB','4x4 and forest roads','Numbered Forest Service roads only \\u2014 the class that takes a full-size pickup. Every T-numbered route on this district is 50-inch width and excludes the truck.', routes(c.offroad))
    + sec('\\uD83D\\uDE99','Scenic drives','Day trips in the towed truck. The coach does not leave the campground.', routes(c.scenicDrives))
    + sec('\\uD83D\\uDCF7','Shot list','Vantage and hour worked against these dates and this latitude.', shots)
    + light
    + sec('\\u26FA','Camp \\u2014 the 40 ft question','Not one operator publishes a maximum length, so every one is a phone call before booking.', camps)
    + '</div>';
})();
</script>
''' + VIEW_END
    h = replace_between(h, VIEW_START, VIEW_END, views, '<div class="ext-only hidden">')

    # Write via a temp file and rename. A direct write_text() that raises partway
    # leaves desktop/index.html TRUNCATED — a UnicodeEncodeError on a stray
    # surrogate emptied the 5.9 MB master to 0 bytes here, and only the last
    # commit saved it. Rename is atomic; a failed encode never touches the file.
    # A lone surrogate cannot be encoded as UTF-8, and the write that discovers
    # that has already truncated the file in older versions. Catch it here, where
    # the message can say WHERE it is, instead of at the encoder.
    bad = [i for i, ch in enumerate(h) if 0xD800 <= ord(ch) <= 0xDFFF]
    if bad:
        k = bad[0]
        sys.exit('!! build_cloudcroft: unpaired surrogate at offset %d — %r\n'
                 '   A \\uXXXX escape meant for JavaScript was single-backslashed in this '
                 'script, so Python decoded it instead of passing it through.'
                 % (k, h[max(0, k - 70):k + 10]))

    tmp = SRC.with_suffix('.html.tmp')
    tmp.write_text(h, encoding='utf-8')
    tmp.replace(SRC)
    print(f'build_cloudcroft: {len(db["trails"])} trails, {len(db["offroad"])} 4x4 routes, '
          f'{len(db["cruise"])} cruise entries, {len(db["shots"])} shots, '
          f'{len(db["campgrounds"])} campgrounds injected')


if __name__ == '__main__':
    main()

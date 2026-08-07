#!/usr/bin/env python3
"""
Add the "Ask Claude" tab to the desktop dashboard.

    cd tools && python3 build_askbox.py

Every other way of getting a question from this dashboard to Claude starts with
the person retyping what the dashboard already knows. The plan controls can push
a nights change, the notes box can push a note, and adding a stop hands over a
researched brief — but a plain question ("is Chitina still the right call?") has
no route at all, and answering it means someone typing the stop name, the dates,
the campground, the length, the rating and the phone number back out of a screen
that is already showing all six.

So this tab does one thing: it builds the brief. The free-text box is the small
part. The point is askBrief(), which gathers what is known about a stop from the
five separate layers that each hold a piece of it — the stop record has the dates
and the campground name, CAMPFACTS has the site length and the Google rating and
whether the place is open or even exists, RIGFIT has the verdict on whether the
coach fits, PLAN has whatever has been changed on this device and not published,
ISSUES has anything already flagged, and BOOKINGS has how the site is actually
reserved. Nobody holds all of that in their head at a rest stop.

Two modes, because the two questions are genuinely different. "Make the change"
targets the repo and carries the build contract with it: the consts are
generated, so edit the db and the build script; run the loop twice; gate on the
test; push and let the workflow republish. "Talk it through" says analyse and
recommend, change nothing — which matters, because a question asked from the
roadside should not silently rewrite eighteen months of dates.

The research rules ride along on both. They are in CLAUDE.md, but CLAUDE.md is
in the repo and the talk-mode conversation is not, and "never invent a maximum RV
length" is exactly the rule that gets broken by a model trying to be helpful
about a campground it cannot find. A wrong length strands a 40 ft coach on a road
it cannot turn around on, so the rule travels with every brief rather than
sitting in a file the other end may never read.

WHY THIS IS A SCRIPT AND NOT A HAND EDIT
desktop/index.html is the master, and it is rebuilt constantly. A hand-added tab
survives exactly until the next person runs the build loop and wonders why the
diff is so large. This is re-runnable: run it as often as you like and the file
converges.

THE PATCHING TRAP, WHICH THIS SCRIPT EXISTS TO NOT REPEAT
An earlier attempt at this kind of injection matched the block by its *shape* —
find something that looks like the CSS we wrote, replace it. The regex terminated
at the first blank line after a closing brace, which is nowhere near the end of a
stylesheet block. It left half the old copy in place and appended a complete
second one, and because both copies were valid CSS the page still rendered and
nothing failed. It was only found later, at roughly twice the size.

So every injected region here is delimited by explicit start and end marker
comments, and the replace is between the markers — never by shape, never by
guessing where a block ends. Each region is inserted once at a named anchor and
replaced in place forever after.

Verify it converged:

    md5 ../desktop/index.html
    python3 build_askbox.py && python3 build_askbox.py && python3 build_askbox.py
    # the md5 printed after runs 1, 2 and 3 must be identical

The script prints that md5 itself so the check is one command, not three.

WHAT THIS DOES NOT TOUCH
mobile/index.html. build_mobile.py does not copy the desktop shell — it builds
its own five-tab phone layout and extracts only the data consts out of the
desktop file. So this tab is desktop-only by construction, and adding it cannot
regress the phone build. Run build_mobile.py and build_vendor.py after this one
anyway, because that is the order the publish sequence uses.
"""
import hashlib
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'

# ---- Marker-delimited regions --------------------------------------------
# The whole point. Nothing here is ever matched by shape; every region is found
# by its own markers and replaced between them.
CSS_START = '/* ask-box start — build_askbox.py — do not edit between the markers */'
CSS_END = '/* ask-box end — build_askbox.py */'
TAB_START = '<!-- ask-box tab start — build_askbox.py -->'
TAB_END = '<!-- ask-box tab end — build_askbox.py -->'
VIEW_START = '<!-- ask-box view start — build_askbox.py -->'
VIEW_END = '<!-- ask-box view end — build_askbox.py -->'
JS_START = '/* ask-box js start — build_askbox.py — do not edit between the markers */'
JS_END = '/* ask-box js end — build_askbox.py */'

# The anchors each region is inserted at the first time. After that the markers
# find it and the anchor is not consulted.
TAB_ANCHOR = '<button class="tab-btn" data-view="booking">Booking Board</button>'
VIEW_ANCHOR = '  <section class="view" id="view-reference">'

CSS = r'''
  /* The Ask tab. Deliberately plain — it is a form, and the interesting part is
     the brief it assembles, which is shown in full rather than hidden. */
  #view-ask .ask-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px;align-items:start;}
  @media(max-width:900px){ #view-ask .ask-grid{grid-template-columns:minmax(0,1fr);} }
  .ask-panel{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px 16px;}
  .ask-lab{display:block;font-size:.68rem;text-transform:uppercase;letter-spacing:.05em;
    color:var(--muted);font-weight:700;margin:0 0 5px;}
  .ask-row{margin:0 0 12px;}
  #askScope{width:100%;background:var(--panel2);color:var(--text);border:1px solid var(--border);
    border-radius:7px;padding:7px 9px;font-size:.82rem;font-family:inherit;}
  #askScope:focus{outline:none;border-color:var(--accent);}
  #askText{width:100%;min-height:150px;resize:vertical;background:var(--panel2);color:var(--text);
    border:1px solid var(--border);border-radius:7px;padding:9px 10px;font-size:.86rem;
    line-height:1.5;font-family:inherit;}
  #askText:focus{outline:none;border-color:var(--accent);}
  .ask-modes{display:flex;gap:4px;background:var(--panel2);border:1px solid var(--border);
    border-radius:9px;padding:3px;}
  .ask-mode-btn{flex:1 1 0;background:transparent;border:none;color:var(--muted);font-size:.76rem;
    font-weight:700;padding:7px 10px;border-radius:6px;cursor:pointer;text-align:center;
    transition:background .12s,color .12s;font-family:inherit;}
  .ask-mode-btn:hover{color:var(--text);}
  .ask-mode-btn.on{background:var(--accent);color:#0f1216;}
  .ask-mode-why{font-size:.72rem;color:var(--muted);line-height:1.45;margin:6px 2px 0;}
  .ask-btns{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:12px;}
  .ask-btns button{font-size:.78rem;font-weight:700;padding:7px 14px;border-radius:7px;cursor:pointer;
    background:var(--panel2);color:var(--text);border:1px solid var(--border);font-family:inherit;}
  .ask-btns button:hover{border-color:var(--accent);}
  .ask-btns button.go{background:var(--accent);color:#0f1216;border-color:var(--accent);}
  .ask-count{font-size:.72rem;color:var(--muted);margin:8px 2px 0;line-height:1.45;}
  .ask-count.over{color:#e8b04b;}
  .ask-status{font-size:.72rem;color:#7ec488;margin-left:2px;min-height:1em;}
  #view-ask details{margin-top:12px;border-top:1px solid var(--border);padding-top:10px;}
  #view-ask summary{cursor:pointer;font-size:.76rem;font-weight:700;color:var(--muted);}
  #view-ask summary:hover{color:var(--text);}
  #askPreview{white-space:pre-wrap;word-break:break-word;background:var(--panel2);
    border:1px solid var(--border);border-radius:7px;padding:10px 11px;margin:9px 0 0;
    max-height:460px;overflow:auto;font-family:ui-monospace,Menlo,monospace;
    font-size:.72rem;line-height:1.5;color:var(--text);}
'''

VIEW = r'''
  <section class="view" id="view-ask">
    <p class="subhead" style="margin:0 0 4px">Ask Claude about this trip</p>
    <p style="font-size:.78rem;color:var(--muted);margin:0 2px 12px;max-width:820px">Pick a stop and the
      question goes out with everything already known about it — the dates, the campground, whether the
      coach fits, the Google rating and how old it is, anything already flagged, and how the site is
      actually booked. That is the part worth sending; the typing is the small part. The exact text is
      at the bottom of this page before it goes anywhere.</p>
    <div class="ask-grid">
      <div class="ask-panel">
        <div class="ask-row">
          <label class="ask-lab" for="askScope">What is this about</label>
          <select id="askScope"><option value="">the whole trip</option></select>
        </div>
        <div class="ask-row">
          <label class="ask-lab" for="askText">The question</label>
          <textarea id="askText" placeholder="Ask it the way you would say it out loud. &#10;&#10;&quot;Is Chitina still worth three nights if the Copper River run is late?&quot;&#10;&quot;Find somewhere near Tok that will take the coach in the first week of September.&quot;"></textarea>
          <div class="ask-count" id="askCount"></div>
        </div>
        <div class="ask-row" style="margin-bottom:0">
          <span class="ask-lab">What Claude should do with it</span>
          <div class="ask-modes">
            <button class="ask-mode-btn on" data-mode="repo" type="button">Make the change</button>
            <button class="ask-mode-btn" data-mode="talk" type="button">Talk it through</button>
          </div>
          <p class="ask-mode-why" id="askModeWhy"></p>
        </div>
        <div class="ask-btns">
          <button class="go" onclick="askSend()">Send to Claude</button>
          <button onclick="askCopy()">Copy the brief</button>
          <button onclick="askClear()">Clear</button>
          <span class="ask-status" id="askStatus"></span>
        </div>
      </div>
      <div class="ask-panel">
        <span class="ask-lab">What gets sent</span>
        <p style="font-size:.75rem;color:var(--muted);line-height:1.5;margin:0">Nothing is sent until you
          press the button, and the full text always goes to the clipboard first — so if the app does not
          open, or the link is too long for it, the brief is still sitting there to paste. The link itself
          is capped at the far end, so a long brief is cut in the link and marked where it was cut. The
          clipboard copy is never cut.</p>
        <details open>
          <summary>The exact brief that will be sent</summary>
          <pre id="askPreview"></pre>
        </details>
      </div>
    </div>
  </section>
'''

JS = r'''
// ==================== ASK CLAUDE ====================
// Built by tools/build_askbox.py — see that file for why this exists.
//
// This block sits at the very end of the script on purpose. Everything it
// touches — allStops, allBookings, allIssues, CAMPFACTS, RIGFIT, PLAN,
// CODE_REPO, PUSH_LIMIT, openUrl, copyText, todayISO — is declared above it,
// and a const referenced before its declaration throws rather than reading
// undefined. That trap has cost a blank dashboard three times.
const ASK_KEY = 'alaskaTrip.ask.v1';
const ASK_SAVE_MS = 400;

const ASK_REPO_STEPS = [
  'HOW TO ACT ON THIS — MAKE THE CHANGE:',
  '  Work in the repo: https://github.com/lluisitu/alaska-trip',
  '',
  '  The consts in desktop/index.html (STOPS, EXT_DATA, BOOKINGS, ISSUES, LIGHT,',
  '  PASSES, LEGINFO, COSTS, PETLOG, RIGFIT, CAMPFACTS, KEPT_CAMPS, DRONE, FROZEN,',
  '  ROUTE_GEOM) are GENERATED. Editing one by hand looks like it worked and is',
  '  silently overwritten by the next build. Change the source instead — the',
  '  relevant tools/<name>_db.json plus its build script.',
  '',
  '  Then, from tools/, run the build loop TWICE — some steps read what earlier',
  '  steps wrote, so one pass leaves the file a step behind itself:',
  '    build_strategy build_frozen build_light build_phonecraft build_drone',
  '    build_passes build_legs build_costs build_petlog build_staynotes',
  '    build_rigfit build_campfacts build_swaps build_bookings build_parks',
  '  Then build_routes.py, build_mobile.py and build_vendor.py.',
  '',
  '  Then gate on the suite: node tools/test_alaska_ext_v3.js must print',
  '  "Page errors: 0". If it does not, the change is not finished.',
  '',
  '  Then commit and push to main. That starts .github/workflows/rebuild.yml and',
  '  GitHub Pages republishes on its own — no laptop needed at this end.'
].join('\n');

const ASK_TALK_STEPS = [
  'HOW TO ACT ON THIS — TALK IT THROUGH:',
  '  Analysis and a recommendation only. Change nothing: do not edit the repo, do',
  '  not run the build, do not push. If the answer is that something should change,',
  '  say what and why and let it be decided here first.'
].join('\n');

const ASK_RULES = [
  'RESEARCH RULES — these are not style preferences:',
  '  Never invent a URL, a coordinate or a maximum RV length. If a figure cannot be',
  '  sourced, record it as unknown. An absence gets phoned about; a wrong number',
  '  gets acted on, and a wrong length strands a 40 ft coach on a road it cannot',
  '  turn around on.',
  '  A site must take 40 ft. The truck is towed and parks in overflow or on the',
  '  side, which most parks allow — so only rule a site out when the limit is for',
  '  the coach alone, not the combined length.',
  '  Ratings come from Google or they are null. Not Campendium, not Good Sam —',
  '  different user pools.',
  '  The site is public. Never copy or embed third-party photographs; publishing',
  '  them is republication.'
].join('\n');

const ASK_MODE_WHY = {
  repo: 'Opens Claude Code on the repo. It can research, edit the db files, run the build and the test, and push — GitHub Pages republishes without a laptop.',
  talk: 'Opens a plain conversation. It reads the brief and answers. Nothing in the repo moves.'
};

function askEsc(s){
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function askEl(id){ return document.getElementById(id); }
function askScopeId(){ const e = askEl('askScope'); return e ? e.value : ''; }
function askModeNow(){
  const b = document.querySelector('.ask-mode-btn.on');
  return b ? b.dataset.mode : 'repo';
}
function askRequest(){ const e = askEl('askText'); return e ? e.value.trim() : ''; }

// One line, because the rig is half of every campground answer and it is the
// thing an outside reader never has.
function askTripLine(){
  const all = allStops();
  const nights = all.reduce((a, s) => a + (s.nights || 0), 0);
  const arr = all.map(s => s.arrive).filter(Boolean).sort();
  const dep = all.map(s => s.depart).filter(Boolean).sort();
  return all.length + ' stops, ' + nights + ' nights, ' + (arr[0] || '?') + ' to '
    + (dep[dep.length - 1] || '?') + '. 2005 40 ft Class A motorhome towing a 4x4 pickup, '
    + 'with a dog and a cat aboard.';
}

// A change made on this device but not yet in overrides.json is invisible to
// anyone reading the published dashboard, so the brief has to say so.
function askUnpublishedLine(){
  const n = Object.keys(PLAN.localAll()).length;
  if(!n) return 'UNPUBLISHED CHANGES: none — this dashboard matches what is published.';
  return 'UNPUBLISHED CHANGES: ' + n + ' plan change' + (n === 1 ? '' : 's')
    + ' made on this device and not yet published to overrides.json, so the dates below '
    + 'may already have moved here.';
}

// Everything known about one stop, gathered from the layers that each hold a
// piece of it. Absences are stated rather than skipped — a missing site length
// is a fact worth sending, because it is the one that has to be phoned about.
function askStopBlock(id){
  const s = allStops().find(x => x.id === id);
  if(!s) return [];
  const out = [];
  const camp = PLAN.camp(id) || s.camp || '';
  out.push('THE STOP: ' + s.name + '   [id: ' + s.id + ']');
  out.push('  Published: ' + s.arrive + ' to ' + s.depart + ', ' + s.nights
    + ' night' + (s.nights === 1 ? '' : 's'));

  const d = PLAN.delta(id), sk = PLAN.skipped(id), pc = PLAN.camp(id);
  if(sk) out.push('  PLAN CHANGE: marked skipped on the dashboard — the stop is currently dropped.');
  else if(d) out.push('  PLAN CHANGE: ' + (d > 0 ? '+' : '') + d + ' night'
    + (Math.abs(d) === 1 ? '' : 's') + ' against the published plan.');
  if(pc) out.push('  PLAN CHANGE: campground switched to ' + pc
    + (s.camp ? ' (published: ' + s.camp + ')' : ''));

  const cf = (later(() => CAMPFACTS, {stops: {}}).stops || {})[id];
  out.push('  Campground: ' + (camp || 'none recorded'));
  if(cf){
    if(cf.exists === false) out.push('  ** COULD NOT BE SHOWN TO EXIST — no page, no listing, no phone. **');
    if(cf.open === false) out.push('  ** CLOSED ON THE ARRIVAL DATE. **');
    out.push('  Longest site: ' + (cf.ft != null ? cf.ft + ' ft' : 'not published — unknown, not assumed')
      + (cf.n40 != null ? ' (' + cf.n40 + ' site' + (cf.n40 === 1 ? '' : 's') + ' take 40 ft)' : ''));
    out.push('  Google: ' + (cf.g != null
      ? cf.g + ' from ' + (cf.gn != null ? cf.gn : 'an unrecorded number of') + ' reviews'
        + (cf.gd ? ', read ' + cf.gd : '')
      : 'no rating available — null, not guessed'));
    if(cf.phone) out.push('  Phone: ' + cf.phone);
    if(cf.url) out.push('  Source: ' + cf.url);
    if(cf.alt) out.push('  Better alternative on file: ' + cf.alt.name
      + (cf.alt.distance_mi != null ? ' (' + cf.alt.distance_mi + ' mi away)' : '')
      + (cf.alt.g != null ? ', rated ' + cf.alt.g : '')
      + (cf.alt.why ? ' — ' + cf.alt.why : ''));
    if(cf.notes) out.push('  Research notes: ' + cf.notes);
  } else {
    out.push('  No CAMPFACTS entry for this stop — nothing verified about length, rating or season.');
  }

  const fit = (later(() => RIGFIT, {opts: {}}).opts || {})[id + '|' + camp];
  if(fit){
    out.push('  Rig fit: ' + (fit.label || fit.s || '?') + (fit.src ? '  [' + fit.src + ']' : ''));
    if(fit.s === 'combined-tight') out.push('    combined-tight — the posted limit really is for the '
      + 'coach and the truck together, not the coach alone.');
  } else {
    out.push('  Rig fit: no verdict on file for this campground — treat the length as unknown.');
  }

  const iss = allIssues().filter(i => i.stop_id === id);
  if(iss.length){
    out.push('  Known issues (' + iss.length + '):');
    iss.forEach(i => {
      out.push('    [' + (i.severity || '?') + ' / ' + (i.category || '?') + '] ' + (i.issue || ''));
      if(i.analysis) out.push('       ' + i.analysis);
      if(i.solution) out.push('       -> ' + i.solution);
    });
  }

  const bk = allBookings().find(b => b.id === id);
  if(bk){
    out.push('  Booking route: ' + (bk.system || 'system unknown')
      + (bk.opensISO ? ', window opens ' + bk.opensISO : ', no opening date on file')
      + (bk.opensLocalTime ? ' at ' + bk.opensLocalTime : '')
      + (bk.leadMonths != null ? ', ' + bk.leadMonths + '-month lead' : ''));
    if(bk.critical) out.push('    ** critical window — this one empties within minutes of opening. **');
    if(bk.what) out.push('    Book: ' + bk.what);
    if(bk.phone) out.push('    Phone: ' + bk.phone);
    if(bk.url) out.push('    ' + bk.url);
    if(bk.note) out.push('    ' + bk.note);
  } else {
    out.push('  Booking route: no BOOKINGS entry for this stop.');
  }
  return out;
}

// The whole point of the feature.
function askBrief(){
  const req = askRequest();
  const id = askScopeId();
  const mode = askModeNow();
  const out = ['Ask from the Alaska Trip dashboard — ' + todayISO(), ''];
  out.push(id ? 'THE REQUEST (about one stop):' : 'THE REQUEST (about the whole trip):');
  out.push(req || '(nothing typed yet)');
  out.push('');
  out.push('THE TRIP: ' + askTripLine());
  out.push(askUnpublishedLine());
  out.push('');
  if(id){
    askStopBlock(id).forEach(l => out.push(l));
    out.push('');
  }
  out.push(mode === 'repo' ? ASK_REPO_STEPS : ASK_TALK_STEPS);
  out.push('');
  out.push(ASK_RULES);
  return out.join('\n');
}

function askSetStatus(msg, ms){
  const el = askEl('askStatus');
  if(!el) return;
  el.textContent = msg || '';
  if(msg && ms) setTimeout(() => { if(el.textContent === msg) el.textContent = ''; }, ms);
}

// The counter is the honest answer to "will this arrive whole?" — the link is
// capped at the far end, so say now whether the brief fits it.
function askRenderCount(){
  const el = askEl('askCount');
  if(!el) return;
  const req = askRequest().length;
  const brief = askBrief().length;
  const over = brief > PUSH_LIMIT;
  el.classList.toggle('over', over);
  el.textContent = req + ' character' + (req === 1 ? '' : 's') + ' typed · the brief comes to '
    + brief + (over
      ? ', which is longer than the ' + PUSH_LIMIT + ' a link carries — it will be cut in the link '
        + 'and marked where, and the full text goes to the clipboard.'
      : ', which fits in the link.');
}

function askRenderPreview(){
  const pre = askEl('askPreview');
  if(pre) pre.textContent = askBrief();
  const why = askEl('askModeWhy');
  if(why) why.textContent = ASK_MODE_WHY[askModeNow()] || '';
  askRenderCount();
}

function askSaveNow(){
  try{
    localStorage.setItem(ASK_KEY, JSON.stringify({
      text: askEl('askText') ? askEl('askText').value : '',
      scope: askScopeId(),
      mode: askModeNow()
    }));
  }catch(e){}
}
// Debounced, so a long paragraph is one write and not one per keystroke. The
// counter still updates immediately — it is cheap and it is the feedback.
let _askTimer = null;
function askQueueSave(){
  clearTimeout(_askTimer);
  _askTimer = setTimeout(() => { askSaveNow(); askRenderPreview(); }, ASK_SAVE_MS);
}

function askSetMode(mode){
  document.querySelectorAll('.ask-mode-btn').forEach(b => b.classList.toggle('on', b.dataset.mode === mode));
  askSaveNow();
  askRenderPreview();
}

function askCopy(){
  copyText(askBrief(), null);
  askSetStatus('copied — the full brief is on the clipboard', 6000);
}

function askClear(){
  const t = askEl('askText');
  if(t) t.value = '';
  askSaveNow();
  askRenderPreview();
  askSetStatus('cleared', 3000);
  if(t) t.focus();
}

// Same handoff the rest of the dashboard uses: try the app's scheme, fall back
// to the universal link if nothing handled it. The clipboard copy happens first
// and is never truncated — a button that looked like it worked and quietly
// dropped the tail would be worse than no button.
function askSend(){
  if(!askRequest()){
    alert('Type the question first — the brief is built around it.');
    const t = askEl('askText');
    if(t) t.focus();
    return;
  }
  const full = askBrief();
  copyText(full, null);
  let txt = full;
  if(txt.length > PUSH_LIMIT){
    txt = txt.slice(0, PUSH_LIMIT - 220)
      + '\n\n[TRUNCATED — ' + (full.length - PUSH_LIMIT + 220) + ' more characters did not fit in '
      + 'the link. The complete brief is on the clipboard: paste it over this message.]';
  }
  const q = encodeURIComponent(txt);
  const repo = askModeNow() === 'repo';
  const args = repo
    ? 'q=' + q + '&repo=' + encodeURIComponent(CODE_REPO) + '&mode=code'
    : 'q=' + q;
  const scheme = repo ? 'claude://code/new?' : 'claude://cowork/new?';
  const web = repo ? 'https://claude.ai/code/new?' : 'https://claude.ai/new?';
  askSetStatus(full.length > PUSH_LIMIT
    ? 'opening Claude — too long for the link, so paste over it from the clipboard'
    : 'opening Claude…');
  let handled = false;
  const onHide = () => { handled = true; };
  document.addEventListener('visibilitychange', onHide, {once: true});
  openUrl(scheme + args);
  setTimeout(() => {
    document.removeEventListener('visibilitychange', onHide);
    if(handled || document.hidden) return;
    window.open(web + args, '_blank', 'noopener');
    askSetStatus('opened claude.ai — if the box is empty, paste from the clipboard', 8000);
  }, 1400);
}

function askInit(){
  const sel = askEl('askScope');
  if(!sel) return;
  const group = (list, label) => list.length
    ? '<optgroup label="' + askEsc(label) + '">' + list.map(s =>
        '<option value="' + askEsc(s.id) + '">' + askEsc(s.name)
        + (s.arrive ? ' · ' + askEsc(fmtDate(s.arrive)) : '') + '</option>').join('') + '</optgroup>'
    : '';
  sel.innerHTML = '<option value="">the whole trip</option>'
    + group(STOPS, 'Alaska loop') + group(extStops(), 'Complete East Extension');

  let saved = {};
  try{ saved = JSON.parse(localStorage.getItem(ASK_KEY) || '{}') || {}; }catch(e){ saved = {}; }
  const t = askEl('askText');
  if(t && saved.text) t.value = saved.text;
  // Match the option by value rather than by building a selector — a stop id is
  // not guaranteed to be a valid CSS identifier, and a saved stop that has since
  // been removed from the itinerary must fall back to "the whole trip".
  if(saved.scope && Array.prototype.some.call(sel.options, o => o.value === saved.scope)){
    sel.value = saved.scope;
  }
  if(saved.mode === 'talk' || saved.mode === 'repo'){
    document.querySelectorAll('.ask-mode-btn').forEach(b => b.classList.toggle('on', b.dataset.mode === saved.mode));
  }

  if(t) t.addEventListener('input', () => { askRenderCount(); askQueueSave(); });
  sel.addEventListener('change', () => { askSaveNow(); askRenderPreview(); });
  document.querySelectorAll('.ask-mode-btn').forEach(b =>
    b.addEventListener('click', () => askSetMode(b.dataset.mode)));
  askRenderPreview();
}
document.addEventListener('DOMContentLoaded', () => {
  try{ askInit(); }catch(e){ console.warn('ask-box', e); }
});
'''


def between(h, start, end, block):
    """Replace the region between the markers, or return None if it is absent.

    Matched by the markers and only the markers. The lambda in sub() is not
    decoration — a backslash or a \\g in the replacement would otherwise be read
    as a backreference and corrupt the block silently.
    """
    rx = re.compile(re.escape(start) + r'.*?' + re.escape(end), re.S)
    if not rx.search(h):
        return None
    return rx.sub(lambda _m: block, h, count=1)


def put_at(h, start, end, body, anchor, where):
    """Replace the marked region if it exists, else insert it at the anchor."""
    block = start + body + end
    done = between(h, start, end, block)
    if done is not None:
        return done, 'replaced'
    assert anchor in h, 'anchor not found in desktop/index.html: ' + anchor[:60]
    if where == 'after':
        return h.replace(anchor, anchor + '\n' + block, 1), 'inserted'
    return h.replace(anchor, block + '\n' + anchor, 1), 'inserted'


def put_before_last(h, start, end, body, needle):
    """Same, but anchored at the LAST occurrence of the needle.

    The main stylesheet and the main script are each the second block of their
    kind — build_vendor.py inlines Leaflet into a pair that comes first. Anchoring
    on the first </style> or </script> would inject into Leaflet.
    """
    block = start + body + end
    done = between(h, start, end, block)
    if done is not None:
        return done, 'replaced'
    i = h.rindex(needle)
    return h[:i] + block + '\n' + h[i:], 'inserted'


def main():
    h = SRC.read_text()
    before = hashlib.md5(h.encode()).hexdigest()
    what = {}

    h, what['tab button'] = put_at(h, TAB_START, TAB_END,
                                   '<button class="tab-btn" data-view="ask">Ask Claude</button>',
                                   TAB_ANCHOR, 'after')
    h, what['view'] = put_at(h, VIEW_START, VIEW_END, VIEW, VIEW_ANCHOR, 'before')
    h, what['css'] = put_before_last(h, CSS_START, CSS_END, CSS, '</style>')
    h, what['js'] = put_before_last(h, JS_START, JS_END, JS, '</script>')

    SRC.write_text(h)
    after = hashlib.md5(h.encode()).hexdigest()
    for k in ('tab button', 'view', 'css', 'js'):
        print(f"  {k:<12} {what[k]}")
    print(f"  {'changed' if before != after else 'no change — already converged'}")
    print(f"  md5 {after}  {SRC}")


if __name__ == '__main__':
    main()

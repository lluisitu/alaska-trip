const { chromium } = require('playwright');
const path = require('path');

const LEAFLET_CSS_STUB = `.leaflet-container{background:#000}`;
const LEAFLET_JS_STUB = `
(function(){
  function chain(){
    const obj = {};
    const methods = ['addTo','bindPopup','bindTooltip','unbindTooltip','on','setView','addLayer','removeLayer',
      'invalidateSize','fitBounds','getZoom','setZoom','remove','openPopup','closePopup','eachLayer','getSize',
      'latLngToContainerPoint','getBounds'];
    methods.forEach(m=>{
      obj[m] = function(...args){
        if(m==='getZoom') return 5;
        if(m==='getSize') return {x:600,y:260};
        if(m==='latLngToContainerPoint') return {x:100,y:100};
        if(m==='getBounds') return { getCenter: ()=>({lat:0,lng:0}) };
        window.__mapCalls = window.__mapCalls || [];
        window.__mapCalls.push(m);
        return obj;
      };
    });
    return obj;
  }
  window.L = {
    map: function(){ return chain(); },
    tileLayer: function(){ return chain(); },
    layerGroup: function(){ return chain(); },
    circleMarker: function(){ return chain(); },
    marker: function(){ return chain(); },
    divIcon: function(opts){ return opts; },
    polyline: function(){ return chain(); },
    latLngBounds: function(pts){ return chain(); },
  };
})();
`;

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', msg => { if(msg.type()==='error') errors.push('console: '+msg.text()); });

  await page.route('**/leaflet*.css', route => route.fulfill({ contentType: 'text/css', body: LEAFLET_CSS_STUB }));
  await page.route('**/leaflet*.js', route => route.fulfill({ contentType: 'application/javascript', body: LEAFLET_JS_STUB }));
  await page.route('**tile**', route => route.fulfill({
    contentType: 'image/png',
    body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
  }));

  const filePath = 'file://' + path.resolve(__dirname, '..', 'desktop', 'index.html');
  await page.goto(filePath);
  await page.waitForTimeout(800);

  const title = await page.title();
  console.log('Title:', title);

  // ---- Nav structure: 4 tabs, no 5th "Complete East Extension" tab ----
  const navBtnCount = await page.locator('nav.tabs .tab-btn').count();
  console.log('Nav tab count (expect 4):', navBtnCount);
  const oldExtTabCount = await page.locator('button[data-view="ne-extension"]').count();
  console.log('Old "Complete East Extension" nav tab still present (expect 0):', oldExtTabCount);

  // ---- Main loop stop count (expect 98 -- Palo Duro and Tucumcari removed) ----
  const mainStopCards = await page.locator('#cardsWrap .card').count();
  console.log('Main Alaska stop cards (expect 98):', mainStopCards);
  const paloDuroCard = await page.locator('#card-palo-duro').count();
  const tucumcariCard = await page.locator('#card-tucumcari').count();
  console.log('Palo Duro card removed (expect 0):', paloDuroCard);
  console.log('Tucumcari card removed (expect 0):', tucumcariCard);

  // ---- Mileage-to-next on main card ----
  const caprockMeta = await page.locator('#card-caprock-canyons .card-meta').textContent();
  console.log('Caprock Canyons card-meta mentions mileage to next (expect true):', caprockMeta.includes('mi to next stop'));
  console.log('  -> text:', caprockMeta.trim());

  // ---- Main map: State Parks tab + multi-select (regression) ----
  await page.click('#mapTabs button[data-maptab="state"]');
  await page.waitForTimeout(150);
  const mainSpLegend = await page.locator('#spLegend').textContent();
  console.log('Main state-parks legend (expect 44):', mainSpLegend);
  await page.click('#mapTabs button[data-maptab="state"]');
  await page.waitForTimeout(150);

  // ==================== Trip-mode toggle: stays on current tab, doesn't force navigation ====================
  console.log('\n--- Toggling to extension mode while on Overview & Map tab ---');
  await page.click('#tripToggle button[data-trip="extension"]');
  await page.waitForTimeout(300);
  const activeViewAfterToggle = await page.evaluate(()=>document.querySelector('section.view.active').id);
  console.log('Active view after toggle (expect view-overview -- toggle must NOT change tab):', activeViewAfterToggle);
  const statsAfterToggle = await page.locator('#statsRow .n').allTextContents();
  console.log('Shared statsRow after toggle to extension (expect 56 first):', statsAfterToggle);
  const bigloopMapHidden = await page.locator('#view-overview .bigloop-only').evaluate(el=>el.classList.contains('hidden'));
  const extMapShown = await page.locator('#view-overview .ext-only').evaluate(el=>!el.classList.contains('hidden'));
  console.log('Bigloop overview content hidden (expect true):', bigloopMapHidden);
  console.log('Extension overview content shown (expect true):', extMapShown);
  const mapCallsAfterToggle = await page.evaluate(()=>window.__mapCalls || []);
  console.log('Leaflet map calls fired after toggle (expect to include invalidateSize/fitBounds):', mapCallsAfterToggle.slice(-6));

  console.log('\n--- Clicking All Stops tab while still in extension mode ---');
  await page.click('.tab-btn[data-view="stops"]');
  await page.waitForTimeout(300);
  const extCardsVisible = await page.locator('#extCardsWrap .card').count();
  console.log('Extension stop cards visible (expect 56):', extCardsVisible);
  const bigloopStopsHidden = await page.locator('#view-stops .bigloop-only').evaluate(el=>el.classList.contains('hidden'));
  console.log('Bigloop stops content hidden while in extension mode (expect true):', bigloopStopsHidden);
  const charlestonGone = await page.locator('#ext-card-charleston-sc').count();
  console.log('charleston-sc card gone (Winter Coast removed, expect 0):', charlestonGone);
  const chattanoogaMeta = await page.locator('#ext-card-chattanooga-tn .card-meta').textContent();
  console.log('Chattanooga card-meta mentions mileage to next (expect true):', chattanoogaMeta.includes('mi to next stop'));

  console.log('\n--- Clicking Highlights & Weather tab while still in extension mode (mode must persist) ---');
  await page.click('.tab-btn[data-view="highlights"]');
  await page.waitForTimeout(300);
  const extHlCards = await page.locator('#extHighlightsWrap .hl-card').count();
  console.log('Extension highlight cards rendered (expect > 0):', extHlCards);
  const extRollupCounts = await page.locator('#extWeatherRollup .rollup-count').count();
  console.log('Extension weather-rollup count boxes (expect 3):', extRollupCounts);
  const bigloopHlHidden = await page.locator('#view-highlights .bigloop-only').evaluate(el=>el.classList.contains('hidden'));
  console.log('Bigloop highlights content hidden while in extension mode (expect true):', bigloopHlHidden);

  console.log('\n--- Clicking Known Issues tab while still in extension mode ---');
  await page.click('.tab-btn[data-view="issues"]');
  await page.waitForTimeout(300);
  const extIssueCards = await page.locator('#extIssuesWrap .issue-card').count();
  console.log('Extension known-issue cards (expect 14):', extIssueCards);
  const bigloopIssuesHidden = await page.locator('#view-issues .bigloop-only').evaluate(el=>el.classList.contains('hidden'));
  console.log('Bigloop issues content hidden while in extension mode (expect true):', bigloopIssuesHidden);
  const wintercoastIssueGone = await page.evaluate(()=>{
    const cards = Array.from(document.querySelectorAll('#extIssuesWrap .issue-card'));
    return cards.some(c=>c.textContent.includes('beach driving'));
  });
  console.log('Stale beach-driving-caution issue removed (expect false):', wintercoastIssueGone);
  const newWinterCoastIssue = await page.evaluate(()=>{
    const cards = Array.from(document.querySelectorAll('#extIssuesWrap .issue-card'));
    return cards.some(c=>c.textContent.includes('Winter Coast & Gulf stage'));
  });
  console.log('New "Winter Coast & Gulf removed" issue present (expect true):', newWinterCoastIssue);

  console.log('\n--- Toggling back to bigloop mode while on Known Issues tab (tab should NOT change) ---');
  await page.click('#tripToggle button[data-trip="bigloop"]');
  await page.waitForTimeout(300);
  const activeViewAfterToggleBack = await page.evaluate(()=>document.querySelector('section.view.active').id);
  console.log('Active view after toggle back (expect view-issues -- still on Known Issues tab):', activeViewAfterToggleBack);
  const mainIssueCards = await page.locator('#issuesWrap .issue-card').count();
  console.log('Main dashboard issue cards visible again (expect 21):', mainIssueCards);
  const extIssuesHiddenNow = await page.locator('#view-issues .ext-only').evaluate(el=>el.classList.contains('hidden'));
  console.log('Extension issues content hidden after toggling back (expect true):', extIssuesHiddenNow);

  console.log('\n--- Navigating back to Overview & Map tab (still bigloop mode) — map should re-fit ---');
  await page.click('.tab-btn[data-view="overview"]');
  await page.waitForTimeout(300);
  const mainMapVisible = await page.locator('#view-overview .bigloop-only').evaluate(el=>!el.classList.contains('hidden'));
  console.log('Main map content visible again (expect true):', mainMapVisible);

  console.log('\nPage errors:', errors.length);
  errors.forEach(e => console.log('  ERR:', e));

  await browser.close();
  process.exit(errors.length ? 1 : 0);
})();

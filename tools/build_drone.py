#!/usr/bin/env python3
"""
Say, on every stop, whether a drone can legally fly there.

    cd tools && python3 build_drone.py

Why this belongs in the build rather than in prose somewhere. The question that
gets you fined is not "what does the app say about the airspace" - it is "who
administers this ground". B4UFLY and DJI answer the first question; the second
is a land-management fact that no flight app carries, and the US Fish and
Wildlife Service says outright not to rely on those apps for refuge boundaries.

So each stop carries a verdict, the land manager it follows from, the rule in
the manager's own words, and - the part that is actually useful - the nearest
legal alternative when the marquee subject is closed. Roughly half the famous
subjects on this route are inside a national park, and a national park is the
one land category with a categorical ban at any weight.

STATUS VOCABULARY
  yes    - generally legal for recreational flight, subject to the FAA basics
  no     - the subject you came for is closed
  alt    - the marquee is closed, but a legal near-equivalent is within reach
  permit - legal only with a permit arranged in advance
  check  - land manager not established here; establish it before flying

Nothing in here is legal advice, and every rule is quoted from the managing
agency. Verify before flying: compendia and state park policies change.

Standard library only; no network.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'


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


# The rules, quoted once and referenced by key, so the same words appear on
# every stop they govern and a correction only has to be made in one place.
RULES = {
 'nps': ("National Park Service",
   "\"Launching, landing, or operating an unmanned aircraft from or on lands and waters administered "
   "by the National Park Service within the boundaries of [park] is prohibited.\" 36 CFR 1.5 closure, "
   "in every park's compendium. No weight threshold — a 249 g Mini is as banned as a Mavic. "
   "Misdemeanour: up to six months and $5,000. Policy Memorandum 14-05 was rescinded and folded into "
   "Reference Manual 60 Chapter 12; the closures themselves are unchanged."),
 'fws': ("US Fish and Wildlife Service",
   "\"Launching, landing or disturbing wildlife by aircraft (drones) on national wildlife refuges is "
   "prohibited by law.\" 50 CFR 27.34 and 27.51. FWS also warns not to rely on B4UFLY, AirMap or DJI "
   "to show refuge boundaries — they frequently do not."),
 'usfs': ("US Forest Service",
   "\"Members of the public may fly UAS for hobby or recreation in many places on National Forest "
   "System lands\" — no permit for recreational flying. But designated Wilderness is a hard "
   "exclusion: drones are \"both 'motorized equipment' and 'mechanical transport'\" and cannot take "
   "off from, land in, or be operated from congressionally designated Wilderness."),
 'blm': ("Bureau of Land Management",
   "Generally permitted for recreation. Two limits: no launching or landing in designated Wilderness, "
   "and BLM treats takeoff and landing as subject to OHV route designations — launch from a "
   "designated road or route, not cross-country. Wilderness Study Areas are not automatically closed "
   "but the field office may close them."),
 'parkscan': ("Parks Canada",
   "\"All Parks Canada places are 'no drone zones' for recreational use.\" Fine up to $25,000. "
   "Permits exist only for resource management, public safety and vetted commercial filming."),
 'bcparks': ("BC Parks",
   "\"Operating drones without permission is strictly illegal in all BC Parks.\""),
 'ontario': ("Ontario Parks",
   "Landing an aircraft in the park is prohibited, and \"unmanned air vehicles (UAVs) and drones are "
   "not permitted to land\" — which amounts to no legal flight originating inside."),
 'canada-any': ("Transport Canada",
   "Before any of this matters: a US Part 107 is not accepted. \"As a foreign pilot flying a drone "
   "weighing 250 grams or more in Canada, you need a Canadian drone pilot certificate, even if you "
   "are authorized to fly drones in your home country.\" And foreign pilots cannot register an "
   "aircraft at all, so a Foreign SFOC-RPAS is also required — 30 business days. A sub-250 g drone "
   "appears to sidestep both, but confirm that with Transport Canada directly."),
 'tx': ("Texas Parks & Wildlife",
   "Only two Texas state parks have drone zones; anywhere else needs a filming permit that takes "
   "several weeks."),
 'az': ("Arizona State Parks",
   "\"The current rule is all recreational drone use is prohibited in state parks.\""),
 'ut-sp': ("Utah State Parks",
   "Park by park. Dead Horse Point is the template: prohibited March-October, permit-only at $10/day "
   "November-February, and never at the main viewpoint."),
 'sd': ("South Dakota GFP",
   "Recreational use is permitted on GFP property subject to conditions — no surveillance, no "
   "interference with management, no wildlife harassment. The most permissive state system on this "
   "route."),
 'mi': ("Michigan DNR",
   "Recreational use permitted, but not within 100 yards of cultural or historical sites, and not "
   "over the Tahquamenon Falls or Palms Book viewing platforms, occupied beaches, campgrounds or "
   "restrooms."),
 'mn': ("Minnesota DNR",
   "\"It is unlawful to land any aircraft on lands or water totally within the boundaries of any "
   "state park.\" The DNR says operating under that prohibition is not practical and discourages it."),
 'wi': ("Wisconsin DNR",
   "\"The use of unmanned aerial vehicles (UAVs), also known as drones … is prohibited, except where "
   "posted for their use.\" Only one designated area exists statewide."),
 'ar': ("Arkansas State Parks",
   "A permit is required to operate a drone; there is no general recreational right."),
 'me': ("Maine Bureau of Parks & Lands",
   "\"The general use of drones (UAS) is prohibited in Maine State Parks, Historic Sites, or DACF "
   "Boat Launches without direct oversight and guidance.\" The permit requires liability insurance "
   "naming the State of Maine."),
 'ma': ("Massachusetts DCR",
   "Permission or a permit is required on DCR property; there is no recreational right."),
 'vt': ("Vermont FPR",
   "\"Prohibited in State Park and State Forest lands and facilities, unless written permission is "
   "provided by the Commissioner.\""),
 'or-sp': ("Oregon State Parks",
   "All state park property and the entire ocean shore is closed except in designated areas. That "
   "regime changed on 8 August 2026 and opens some properties permit-free — check the current list."),
 'ca-sp': ("California State Parks",
   "Recreational flying is allowed by default in State Parks, Beaches and SRAs \"except where "
   "prohibited by a District Superintendent's posted order\", with wilderness and natural preserves "
   "excluded. Check for a posted order at the unit."),
 'nv-sp': ("Nevada State Parks",
   "Valley of Fire: \"not allowed … unless you have an approved Photography Permit.\""),
 'ny-sp': ("New York State Parks", "A permit is required."),
 'town': ("Municipal / private land",
   "No federal land closure applies, so the FAA basics govern: 400 ft AGL, visual line of sight, "
   "LAANC for controlled airspace, and nothing over people or moving vehicles. Get the landowner's "
   "permission where the launch point is private."),
}

# Per stop: (status, rule key, what you would actually be flying, alternative)
# Classified from the marquee subject, not the campground — the question is
# whether you can fly the thing you came for.
D = {
 # ---- main trip, outbound -------------------------------------------------
 'caprock-canyons': ('no','tx','The canyon rim and the bison herd','None nearby. Texas is the most closed state park system on the route.'),
 'santafe': ('yes','town','Cochiti Lake and the Rio Grande corridor','Kasha-Katuwe Tent Rocks is BLM but has its own closure — check before flying.'),
 'great-sand-dunes': ('alt','nps','The dunefield — the single best drone subject on the outbound leg, and closed','No Colorado alternative. Imperial Sand Dunes (BLM) at the Imperial Dam stop in Jan 2028 is the dune answer for the whole trip, and it is bigger.'),
 'salida-buenavista': ('yes','usfs','The Arkansas River valley and the Collegiate Peaks, on San Isabel NF land','Stay outside the Collegiate Peaks Wilderness.'),
 'estes-rmnp': ('no','nps','Moraine Park, the elk meadows, Trail Ridge','Roosevelt NF land east of the park boundary is legal outside wilderness.'),
 'saratoga': ('yes','town','The North Platte oxbows and the hot pool','Medicine Bow NF nearby, outside the Savage Run and Platte River wilderness areas.'),
 'flaming-gorge': ('yes','usfs','Red Canyon and the incised meanders of the Green River — the best legal aerial on the main trip','Ashley National Forest. From the rim you see a wall; from 300 ft you see the whole horseshoe.'),
 'wind-river': ('yes','usfs','The Green River and Boulder valley, Bridger-Teton NF','The Bridger Wilderness is closed — everything above the trailheads.'),
 'twin-falls': ('check','town','Shoshone Falls and the Snake River Canyon rim','The falls are city-managed with an entry fee; establish the launch point rule. Bruneau Dunes SP is an Idaho alternative.'),
 'sawtooth-nra': ('yes','usfs','The Sawtooth Valley, Salmon River and Stanley Basin','Sawtooth NRA. The Sawtooth Wilderness itself is closed — the peaks, not the valley.'),
 'craters-of-the-moon': ('alt','nps','The NPS loop road and cinder cones are closed','The BLM-managed 750,000-acre portion and the Great Rift — a 52-mile fissure with kipukas — is legal, and is the better aerial subject anyway. Needs the 4x4.'),
 'grand-teton': ('no','nps','Oxbow Bend, Snake River bends, Moulton Barn','Bridger-Teton NF outside wilderness, east of the park.'),
 'west-yellowstone': ('yes','usfs','The Madison valley and Hebgen Lake on Gallatin NF land','Not the park — the boundary is close and the closure is absolute.'),
 'yellowstone': ('no','nps','Grand Prismatic, the Lower Falls, the Lamar','Nothing comparable outside. Grand Prismatic from the air is the picture everyone wants and nobody may legally take.'),
 'bozeman': ('yes','town','The Gallatin valley farmland geometry','Gallatin NF for terrain, outside the wilderness areas.'),
 'glacier': ('no','nps','Going-to-the-Sun, Lake McDonald, the Garden Wall','Flathead NF west of the park.'),
 # ---- Canada --------------------------------------------------------------
 'waterton': ('no','parkscan','Upper Waterton Lake and the Prince of Wales','None. And the Transport Canada certification problem applies before this even matters.'),
 'banff': ('no','parkscan','Moraine Lake, Lake Louise, the Bow valley','None.'),
 'jasper': ('no','parkscan','Athabasca Glacier, Maligne Lake, Spirit Island','None.'),
 'dawson-creek': ('check','canada-any','Mile 0 and the Peace River farmland','Municipal land, so no park closure — but the Canadian certificate and SFOC apply first.'),
 'fort-nelson': ('check','canada-any','Boreal forest and the Alaska Highway corridor','Crown land, no park closure. Certification applies.'),
 'muncho-lake': ('no','bcparks','The jade-green lake against the Terminal Range','None. This is one of the four best subjects on the Alaska Highway and BC Parks closes all of them.'),
 'liard': ('no','bcparks','The hot springs and the boreal wetland','None.'),
 'watson-lake-1': ('check','canada-any','The Sign Post Forest','Municipal. Certification applies.'),
 'whitehorse-1': ('check','canada-any','The Yukon River and Miles Canyon','Territorial and municipal land, no park closure. Certification applies, and Whitehorse airport airspace is right there.'),
 'kluane-1': ('no','parkscan','The Kluane icefields and the Alsek Range','None. The largest non-polar icefield in the world, and closed.'),
 # ---- Alaska --------------------------------------------------------------
 'tok-1': ('yes','town','The Tanana valley and the highway corridor','Low-flying bush and float traffic everywhere in Alaska — assume something with a person in it may be at 300 ft.'),
 'fairbanks-1': ('check','town','The Chena and Tanana river braids','Fairbanks International and Eielson AFB airspace — LAANC before anything.'),
 'talkeetna': ('caution','town','The Susitna, Chulitna and Talkeetna river confluence — genuinely superb braided-river geometry','Talkeetna is the base for Denali flightseeing: a constant stream of low ski-planes and helicopters. Fly early, stay low, keep visual line of sight tight.'),
 'anchorage': ('check','town','Ship Creek and the Cook Inlet mudflats','Class C airspace — LAANC required.'),
 'cooper-landing': ('yes','usfs','The Kenai River and Kenai Lake, Chugach NF','Kenai NWR is adjacent and closed — know which side of the line you are on.'),
 'seward': ('yes','town','Resurrection Bay and the harbour','Kenai Fjords NP is closed. The bay itself outside the park is fine.'),
 'ninilchik': ('yes','town','The bluff, the village church and Cook Inlet','Kenai NWR is inland and closed.'),
 'homer': ('yes','town','Homer Spit — a 4.5-mile gravel finger into Kachemak Bay with the Kenai Mountains behind','There is no ground position from which the spit reads as a spit. Watch Homer airport and the float traffic.'),
 'denali': ('no','nps','The Alaska Range, Polychrome, the braided Toklat','Denali State Park at Trapper Creek is a separate unit — check Alaska State Parks rules there.'),
 'trapper-creek': ('check','town','The Denali view across the Chulitna','Denali State Park — establish the Alaska State Parks rule before flying. The park itself is not NPS.'),
 'palmer': ('yes','town','Matanuska Glacier — medial moraines, crevasse fields and meltwater braids','Private land with paid access, so ask the operator. The only glacier on the route you can legally fly: Kluane, Denali and Wrangell-St Elias are all shut.'),
 'valdez': ('yes','town','Prince William Sound, the harbour and the pipeline terminus','Worthington Glacier is a State Recreation Site — check. Do not fly near the terminal.'),
 'chitina': ('yes','town','The Copper River and the fish wheels','Wrangell-St Elias begins just east and is closed.'),
 'mccarthy': ('no','nps','Kennecott mill town and the Root Glacier — inside Wrangell-St Elias','The most photogenic ghost town on the route, and closed. McCarthy townsite itself is private inholding; ask locally.'),
 'fairbanks-2': ('check','town','The Dalton Highway corridor and the pipeline','LAANC for Fairbanks airspace. North of town the corridor is state and BLM land.'),
 'tok-2': ('yes','town','The Tanana valley on the return','Same as the outbound Tok stop.'),
 'kluane-2': ('no','parkscan','The Kluane icefields','None.'),
 'whitehorse-2': ('check','canada-any','The Yukon River and Miles Canyon','Certification applies; Whitehorse airport airspace is close.'),
 'whitehorse-3': ('check','canada-any','The Yukon River and Miles Canyon','Certification applies; Whitehorse airport airspace is close.'),
 'watson-lake-2': ('check','canada-any','The Sign Post Forest','Municipal. Certification applies.'),
 'dawson-city': ('caution','canada-any','The gold dredge tailings — miles of ordered gravel worms that only read from the air','A superb aerial subject on municipal and crown land, so no park closure. But the Canadian certificate and Foreign SFOC apply, which is why this is the one Canadian subject that might justify a sub-250 g machine.'),
 'boya-lake': ('no','bcparks','The turquoise lake and its islands','None.'),
 'dease-lake': ('no','bcparks','Kinaskan Lake','The Cassiar highway corridor itself is crown land.'),
 'stewart-hyder': ('caution','canada-any','Salmon Glacier — the fifth-largest in Canada and a genuine plan-view subject','Crown land, not a park, so no closure — but certification applies on the Canadian side. The Hyder side is Tongass NF, USFS, and legal.'),
 'smithers': ('check','canada-any','The Bulkley valley and Hudson Bay Mountain','Municipal and crown land. Certification applies.'),
 'prince-george': ('check','canada-any','The Fraser and Nechako confluence','Certification applies. Do not fly near the mills or the airport approach.'),
 'clearwater': ('no','bcparks','Helmcken Falls — a 141 m plunge into a punchbowl','None. One of the great aerial subjects in BC and closed.'),
 'osoyoos': ('check','canada-any','The Okanagan vineyard geometry and the lake','Private and municipal land — vineyard geometry is a strong aerial subject and this is one of the few Canadian ones that is legal once certified.'),
 # ---- Pacific Northwest and California ------------------------------------
 'winthrop': ('yes','usfs','Washington Pass, the Liberty Bell spires and the larch mosaic','Okanogan-Wenatchee NF. Stay outside the Lake Chelan-Sawtooth and Pasayten Wilderness — the highway corridor is fine.'),
 'packwood': ('alt','nps','Rainier itself is closed','Gifford Pinchot NF outside wilderness gives you the mountain from a distance and the valley fog.'),
 'silver-lake': ('alt','usfs','The crater core is closed — Gifford Pinchot extends its aircraft-landing prohibition to drones in Areas One, Two, Three and the Mount Margaret Backcountry','The rest of Gifford Pinchot NF is open, and the blast-zone geometry outside those areas is the subject anyway.'),
 'olympic': ('alt','nps','Hurricane Ridge and the coast strip are closed','Olympic National Forest outside wilderness. Salt Creek is county land — check locally.'),
 'forks': ('alt','nps','Rialto and Ruby Beach are within Olympic NP','DNR and state forest land inland. The sea stacks themselves are park.'),
 'long-beach': ('permit','or-sp','The 28-mile beach and the Columbia bar','Washington, not Oregon — but Cape Disappointment is a state park. Check the Washington State Parks rule for the launch point.'),
 'cannon-beach': ('no','fws','Haystack Rock is Oregon Islands NWR — 1,854 rocks, reefs and islands along the whole coast','Flushing nesting seabirds draws a fine regardless of where you launched.'),
 'white-salmon': ('check','usfs','The Columbia Gorge and the White Salmon River','The Gorge is a National Scenic Area with its own rules; establish them. Gifford Pinchot NF above is straightforward.'),
 'welches': ('yes','usfs','Mount Hood from the Salmon River valley, Mt Hood NF','Outside the Mount Hood Wilderness, which covers the mountain itself.'),
 'bend': ('yes','usfs','The Deschutes, the volcanic buttes and Newberry','Deschutes NF outside the Three Sisters Wilderness. La Pine is a state park — Oregon rules apply there.'),
 'newport': ('permit','or-sp','Yaquina Head and the bay bridge','Oregon closes all state park property and the ocean shore except designated areas — check the list that changed on 8 Aug 2026. Yaquina Head is a BLM outstanding natural area.'),
 'bandon': ('alt','fws','The sea stacks are Oregon Islands NWR','Seven Devils and Devils Kitchen, just south, is one of the properties Oregon opened permit-free from 8 August 2026 — the only legal sea-stack option on that coast.'),
 'crescent-city': ('alt','nps','Redwood NP is closed','State forest and county land outside. The redwood canopy from above is a real subject where it is legal.'),
 'fort-bragg': ('check','ca-sp','The Mendocino headlands and Glass Beach','California allows recreational flying in state parks by default unless a district superintendent has posted otherwise — check for a posted order.'),
 'marina': ('check','ca-sp','Marina dunes and the Monterey bay curve','Monterey airspace needs LAANC. Monterey Bay NMS has overflight rules — establish them.'),
 'yosemite': ('no','nps','The Valley, Half Dome, the falls','Sierra and Stanislaus NF outside wilderness, at a distance.'),
 'sequoia-kings-canyon': ('no','nps','The groves and the Kings Canyon gorge','Sequoia NF outside wilderness.'),
 'lone-pine': ('yes','blm','Alabama Hills National Scenic Area — boulder arches with the whole Sierra escarpment and a snow-covered Whitney behind','One of the best legal aerials on the trip, and winter sun is low all day. The aerial reveals the pattern in the weathered granite that ground shots reduce to individual rocks.'),
 'death-valley': ('no','nps','Badwater, Mesquite Flat, Racetrack Playa','Nothing comparable. The salt polygons are the aerial subject and they are inside the park.'),
 'vegas-area': ('yes','blm','Red Rock Canyon NCA — BLM confirms visitors can fly for recreation','Outside the La Madre and Rainbow Mountain Wilderness. Valley of Fire is a Nevada state park and needs an approved Photography Permit.'),
 'joshua-tree': ('alt','nps','The park is closed','BLM land south and east of the park, including the Joshua Tree South dispersed area.'),
 'borrego-springs': ('check','ca-sp','The badlands, the slot canyons and the Galleta Meadows sculptures','Anza-Borrego is a California state park, so allowed by default unless posted — but check, and the sculptures are on private land.'),
 'imperial-dam': ('yes','blm','Imperial Sand Dunes — the dune answer for the whole trip, half an hour away','Sand at low sun from directly overhead is one of the few subjects genuinely better from the air. Imperial NWR itself is closed.'),
 'yuma-az': ('check','town','The Colorado at the crossing and the prison','Yuma has MCAS and international airport airspace — LAANC first.'),
 'kofa-nwr': ('no','fws','Palm Canyon and the Kofa range','Surrounding BLM land in the Yuma and Imperial Dam area is legal.'),
 'organ-pipe-ajo': ('alt','nps','The monument is NPS-managed and closed','BLM land around Ajo, and the Ajo open-pit mine is a strong aerial subject on non-park ground — establish the owner.'),
 'tucson': ('check','town','The saguaro forest and the aircraft boneyard','Saguaro NP is closed. Davis-Monthan airspace covers the boneyard — do not.'),
 'catalina-state-park': ('no','az','The Santa Catalina front range','Coronado NF land outside the Pusch Ridge Wilderness.'),
 'chiricahua-willcox': ('alt','nps','The rhyolite spires inside the monument are closed','Coronado NF outside the Chiricahua Wilderness has the same rock. Willcox Playa is a separate subject.'),
 'bisbee-tombstone': ('check','town','The Lavender Pit — a genuine plan-view subject','Town and private land; ask. Not a park.'),
 'patagonia-sonoita': ('check','az','The grassland and the lake','Patagonia Lake is an Arizona state park and therefore closed. Coronado NF and the grassland roads are the alternative.'),
 'superior-globe': ('no','az','Lost Dutchman and the Superstition front','Tonto NF outside the Superstition Wilderness.'),
 'camp-verde': ('yes','usfs','The red rock country from Coconino NF land','Outside the Red Rock-Secret Mountain and Munds Mountain Wilderness. Dead Horse Ranch is a Utah-style state park — Arizona bans recreational flying in it.'),
 'grand-canyon': ('no','nps','The canyon','Nothing. And the FAA asks all aircraft to stay 2,000 ft AGL over NPS land, which is above your ceiling anyway.'),
 'zion': ('no','nps','The canyon and the Watchman','BLM land outside the park boundary, west of Virgin.'),
 'great-basin': ('no','nps','Wheeler Peak and the bristlecones','Humboldt-Toiyabe NF outside wilderness.'),
 'bryce': ('alt','nps','The amphitheatre is closed','Dixie NF and the BLM ground east of the park. Grand Staircase-Escalante is BLM-managed and publishes a drone fact sheet that assumes you may fly.'),
 'torrey': ('alt','nps','Capitol Reef is closed','Fishlake NF and the BLM land along the Burr Trail.'),
 'moab': ('yes','blm','Fisher Towers, Onion Creek, Castle Valley, Gemini Bridges, the Shafer switchbacks','The highest-yield week on the route. Arches, Canyonlands and Dead Horse Point are all closed — Dead Horse Point bans it March-October anyway — but the BLM land around them is the same geology with no closure.'),
 'black-canyon-gunnison': ('no','nps','The gorge','Gunnison NF and BLM land outside.'),
 'ouray': ('yes','usfs','The Uncompahgre gorge, the box canyon and the mine roads','Uncompahgre NF outside the Mount Sneffels Wilderness.'),
 'mancos': ('no','nps','The cliff dwellings','San Juan NF outside. Do not fly over any archaeological site.'),
 'durango': ('yes','usfs','The Animas valley and the railway','San Juan NF outside wilderness.'),
 'pagosa-springs': ('yes','usfs','The San Juan River and the hot springs terraces','San Juan NF. The Weminuche Wilderness is closed.'),
 # ---- east trip -----------------------------------------------------------
 'salida-co': ('yes','usfs','The Arkansas valley and Browns Canyon','Browns Canyon is a BLM/USFS national monument, not NPS — but check the current management plan.'),
 'buena-vista-co': ('yes','usfs','The Collegiate Peaks from the valley','San Isabel NF outside the Collegiate Peaks Wilderness.'),
 'leadville-co': ('yes','usfs','The Arkansas headwaters and the mine landscape above Leadville','San Isabel NF outside wilderness.'),
 'wind-river-ext': ('yes','usfs','Fremont Lake and the Green River','Bridger-Teton NF. The Bridger Wilderness is closed.'),
 'scottsbluff-ne': ('alt','nps','Scotts Bluff National Monument is NPS-managed and closed','Wildcat Hills State Recreation Area and the surrounding farmland. Nebraska state park rules — establish them.'),
 'custer-sd': ('yes','sd','Custer State Park — the most permissive state park system on the route','Fly courteously and well away from the bison herds. Mount Rushmore and Jewel Cave are NPS and closed.'),
 'badlands-sd': ('alt','nps','The Badlands wall inside the park is closed','Buffalo Gap National Grassland (USFS) wraps the park — same wall, same light, legal. The Pinnacles dispersed area sits just outside the entrance station.'),
 'medora-nd': ('alt','nps','Theodore Roosevelt NP is closed','Little Missouri National Grassland (USFS), the largest in the country, surrounds the park with the same badlands.'),
 'bismarck-nd': ('no','check','The Missouri and the On-A-Slant village','Fort Abraham Lincoln is a North Dakota state park — establish the rule. The shot list already warns that drone use is prohibited on the NPS portion.'),
 'itasca-mn': ('no','mn','The Mississippi headwaters','Chippewa National Forest is the legal alternative for northern Minnesota forest and lake geometry.'),
 'duluth-mn': ('check','town','The aerial lift bridge and the ship canal — a strong subject','Duluth airspace and a busy working harbour. Jay Cooke is a state park and therefore closed under the Minnesota landing rule.'),
 'grand-marais-mn': ('check','town','The harbour and the Superior shore','Superior National Forest inland is the straightforward legal ground.'),
 'bayfield-wi': ('no','nps','The Apostle Islands sea caves','Chequamegon-Nicolet NF inland. Wisconsin state parks are closed too.'),
 'porcupine-mountains-mi': ('no','mi','Lake of the Clouds','Ottawa National Forest adjoins and is legal outside wilderness.'),
 'marquette-mi': ('check','town','The ore dock and Presque Isle','Municipal land. Hiawatha NF nearby.'),
 'munising-mi': ('no','nps','Pictured Rocks — the cliffs are the aerial subject and they are national lakeshore','Hiawatha National Forest adjoins and is legal.'),
 'tahquamenon-falls-mi': ('permit','mi','The upper falls','Michigan permits recreational flying in state parks but specifically excludes the area over the Tahquamenon Falls viewing platforms. Fly elsewhere in the park.'),
 'st-ignace-mi': ('check','town','The Mackinac Bridge','Bridge authority and airspace rules — establish before flying. Wilderness State Park is Michigan DNR.'),
 'traverse-city-mi': ('yes','mi','The Old Mission and Leelanau orchards and vineyards — farmland geometry, and one of the better legal aerials on the east trip','Sleeping Bear Dunes is NPS and closed. The peninsulas are not.'),
 'door-county-wi': ('no','wi','The shoreline and the bluffs','Wisconsin closes state parks. Private and municipal shoreline only.'),
 'indiana-dunes-in': ('no','nps','The dunes and the steel mills behind them','Indiana Dunes State Park is inside the national park boundary area — establish the state rule separately.'),
 'stratford-on': ('check','canada-any','The Avon and the town','Conservation authority land. Canadian certification applies first.'),
 'elora-on': ('check','canada-any','The Elora Gorge','Conservation authority land, not a provincial park — but certification applies.'),
 'algonquin-on': ('no','ontario','The lakes and the autumn canopy','None inside. Certification applies regardless.'),
 'pec-on': ('no','ontario','Sandbanks dunes','The county vineyards outside the park are private land and a strong subject — with permission, and after certification.'),
 'gananoque-on': ('no','parkscan','The Thousand Islands','Thousand Islands National Park is Parks Canada. Municipal waterfront only.'),
 'perth-on': ('no','ontario','Murphys Point and the Rideau','Certification applies regardless.'),
 'lake-placid-ny': ('check','ny-sp','The High Peaks and the ski jumps','Adirondack Forest Preserve rules are their own thing — establish them. NY state parks need a permit.'),
 'south-hero-vt': ('check','town','Lake Champlain and the island causeway','Vermont closes state parks and state forests without written permission. Private and municipal land only.'),
 'stowe-vt': ('no','vt','Mount Mansfield and Smugglers Notch — both state forest','Green Mountain NF is the legal alternative for Vermont autumn colour, outside wilderness.'),
 'eastern-townships-qc': ('no','check','Mont-Orford','SEPAQ park rules plus Canadian certification. Establish both.'),
 'north-conway-nh': ('yes','usfs','The Saco valley and the Whites','White Mountain NF outside the Presidential Range-Dry River and Great Gulf Wilderness areas.'),
 'bar-harbor-me': ('no','nps','Acadia — the Bubbles, Jordan Pond, the Schoodic coast','Maine state parks are closed too. Private and municipal land in Trenton and Ellsworth only.'),
 'camden-me': ('no','me','Camden Hills and the harbour','Maine closes state parks in practice. The harbour from municipal land, with care.'),
 'berkshires-ma': ('permit','ma','The autumn canopy and the reservoirs','Massachusetts DCR requires permission. October Mountain is DCR land.'),
 'litchfield-hills-ct': ('check','town','The hills and the village greens','Connecticut state park rules — establish. Private land with permission is the straightforward route.'),
 'hudson-valley-ny': ('check','ny-sp','The river, the Hudson Highlands and the estates','NY state parks need a permit. Private land with permission otherwise.'),
 'delaware-water-gap-pa': ('no','nps','The Gap itself','Delaware Water Gap is a National Recreation Area, NPS-managed. State forest land outside.'),
 'gettysburg-pa': ('no','nps','The battlefield','Michaux State Forest nearby — establish the Pennsylvania rule.'),
 'harpers-ferry-wv': ('no','nps','The confluence of the Potomac and Shenandoah — the classic Jefferson Rock view','Nothing comparable. The confluence is the subject and it is park.'),
 'staunton-va': ('no','nps','Shenandoah NP and Skyline Drive','George Washington NF outside wilderness is the legal Blue Ridge alternative.'),
 'lexington-va': ('check','town','The Maury valley and Natural Bridge','Natural Bridge is a Virginia state park — establish the rule. Farmland with permission otherwise.'),
 'new-river-gorge-wv': ('no','nps','The New River Gorge Bridge — the single best aerial subject on the Appalachian leg, and closed','Nothing comparable. The bridge is inside the national park.'),
 'floyd-va': ('check','town','The Blue Ridge farmland','The Parkway is NPS and closed. Private land with permission works well here.'),
 'boone-nc': ('alt','nps','The Parkway viewpoints, Linn Cove Viaduct and Grandfather are closed or private','Pisgah National Forest outside wilderness. Grandfather Mountain is a private attraction — ask.'),
 'asheville-nc-v3': ('yes','usfs','Pisgah NF — Bent Creek, Looking Glass Rock, the Davidson River','The best autumn colour on the east trip and legal, outside the Shining Rock and Middle Prong Wilderness. The Parkway itself is closed.'),
 'bryson-city-nc': ('alt','nps','The Smokies are closed','Nantahala National Forest outside wilderness, and Fontana Lake shoreline.'),
 'chattanooga-tn': ('check','town','The Tennessee River moccasin bend','Chattanooga airspace needs LAANC. Cloudland Canyon is a Georgia state park — establish the rule.'),
 'hot-springs-ar-v3': ('no','nps','Bathhouse Row and the mountain','Ouachita National Forest outside wilderness. Arkansas state parks need a permit.'),
 'petit-jean-ar': ('permit','ar','Cedar Falls and the mountain','Arkansas requires a permit for state park flying. Ouachita and Ozark NF are the free alternative.'),
 'mount-magazine-ar': ('permit','ar','The Petit Jean River valley from the state high point','Same Arkansas permit. Ozark NF surrounds it.'),
 'jasper-ponca-ar': ('alt','nps','The Buffalo National River meanders — the finest in the eastern US, and closed','Ozark-St. Francis National Forest adjoins the corridor. Not the same meanders, but legal Ozark ridgelines.'),
 'mountain-view-ar': ('permit','ar','The Ozark folk landscape','Ozark NF outside the state park.'),
 'eureka-springs-ar-v3': ('check','town','The town on its hillside and Beaver Lake','Private and municipal. Ozark NF nearby.'),
 'bentonville-ar': ('check','town','The trail network and Crystal Bridges','Crystal Bridges is private — ask. Municipal land otherwise.'),
 'devils-den-ar': ('permit','ar','The hollow and the CCC structures','Ozark NF outside the state park.'),
 'mena-ar': ('yes','usfs','Talimena — ridge after parallel ridge of hardwood colour, running east-west so both ends of the day give raking side-light','Ouachita National Forest. Queen Wilhelmina is a state park inside it and needs an Arkansas permit; the forest does not.'),
}

FAA = ("Before any of this: fly under Part 107 rather than the recreational exception if the images may "
       "ever be sold or licensed. 400 ft AGL, visual line of sight, LAANC for controlled airspace, "
       "nothing over people or moving vehicles. Check tfr.faa.gov every morning in fire country — "
       "wildfire TFRs appear with hours of notice and are not always in the app.")


def main():
    h = SRC.read_text()
    stops = json.loads(ex(h, 'const STOPS =', '[', ']'))
    stops += json.loads(ex(h, 'const EXT_DATA ='))['STOPS']

    out, counts, missing = {}, {}, []
    for s in stops:
        if not s.get('nights'):
            continue
        rec = D.get(s['id'])
        if not rec:
            missing.append(s['id']); continue
        status, key, subject, alt = rec
        manager, rule = RULES.get(key, ('Unestablished', 'Establish who administers this ground before flying.'))
        out[s['id']] = {'status': status, 'manager': manager, 'rule': rule,
                        'subject': subject, 'alt': alt}
        counts[status] = counts.get(status, 0) + 1

    if missing:
        sys.exit(f"!! {len(missing)} stops have no drone classification: {missing[:12]}")

    payload = json.dumps({'stops': out, 'faa': FAA}, ensure_ascii=False)
    decl = re.compile(r'const DRONE = \{.*?\};\n', re.S)
    block = f'const DRONE = {payload};\n'
    if decl.search(h):
        h = decl.sub(lambda _m: block, h, count=1)
    else:
        anchor = 'const PHOTO ='
        assert anchor in h, 'PHOTO declaration missing'
        h = h.replace(anchor, block + '\n' + anchor, 1)
    SRC.write_text(h)

    print(f"  {len(out)} stops classified")
    label = {'yes': 'legal', 'no': 'closed', 'alt': 'closed, legal alternative named',
             'permit': 'permit required', 'check': 'land manager to establish',
             'caution': 'legal but hazardous'}
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"     {k:<8}{v:>4}   {label.get(k, '')}")
    print("wrote", SRC)


if __name__ == '__main__':
    main()

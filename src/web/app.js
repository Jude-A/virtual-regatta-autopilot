"use strict";

const SAILS = { 1: "Jib", 2: "Spi", 3: "Trinquette", 4: "Génois léger", 5: "Code 0", 6: "Gennaker lourd", 7: "Gennaker léger" };
const POLL_MS = 15000;
const ALERT_BEFORE_MS = 10 * 60e3;   // notification 10 min avant une action
const SOON_MS = 30 * 60e3;           // action mise en avant 30 min avant
const PLAN_TOL_DEG = 4;              // écart de TWA toléré avant de dire que le bateau ne suit pas le plan
const PLAN_GRACE_MS = 3 * 60e3;      // VR applique une action avec un peu de retard : pas d'alerte juste après
const MAJOR = new Set(["Virement", "Empannage", "Changement de voile"]);
const HORIZONS = [[12, "12 h"], [24, "24 h"], [0, "Tout"]];

// --- Petits utilitaires ---------------------------------------------------

const $ = (id) => document.getElementById(id);
const store = {
  get(key, fallback) {
    try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
  },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* stockage indisponible */ } },
};

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "style") node.style.cssText = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return node;
}

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const sailColor = (id) => cssVar(`--sail-${id}`) || cssVar("--muted");
const sailName = (id) => SAILS[id] || "—";
const baseSail = (id) => (id ? id % 10 : id);  // VR ajoute 10 quand la voile est en mode auto

const nf0 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const dfDayTime = new Intl.DateTimeFormat("fr-FR", { weekday: "short", hour: "2-digit", minute: "2-digit" });
const dfTime = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" });
const dfDay = new Intl.DateTimeFormat("fr-FR", { weekday: "short" });

const dayTime = (ms) => dfDayTime.format(ms).replace(".", "");
const sameDay = (a, b) => new Date(a).toDateString() === new Date(b).toDateString();
const shortTime = (ms) => (sameDay(ms, Date.now()) ? dfTime.format(ms) : dayTime(ms));
const deg = (n) => `${nf0.format(((Math.round(n) % 360) + 360) % 360)}°`;
const signedDeg = (n) => `${n > 0 ? "+" : ""}${nf0.format(n)}°`;
const side = (twa) => (twa < 0 ? "bâbord" : "tribord");

function countdown(ms) {
  if (ms <= 0) return "maintenant";
  const s = Math.round(ms / 1000);
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  if (d) return `${d} j ${h} h`;
  if (h) return `${h} h ${String(m).padStart(2, "0")}`;
  if (m >= 10) return `${m} min`;
  return `${m} min ${String(sec).padStart(2, "0")} s`;
}
function duration(ms) {
  const m = Math.round(ms / 60e3);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`;
}
function ago(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  return s < 60 ? `il y a ${s} s` : `il y a ${Math.round(s / 60)} min`;
}
function isDark() {
  const forced = document.documentElement.dataset.theme;
  return forced ? forced === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
}

// Réglage de la route à l'instant t (dernier point passé)
function routeAt(route, t) {
  let current = route.points[0];
  for (const p of route.points) { if (p.t > t || p.end) break; current = p; }
  return current;
}

// --- Plan de programmation (pilote TWA) ---

const planOf = (race) => race.route?.plan || [];
const twaLocked = (boat) => boat.twaAuto != null && boat.twaAuto !== false;

// Action en cours : la dernière dont l'heure est passée
function currentAction(plan, t) {
  let cur = plan[0] || null;
  for (const a of plan) { if (a.t > t) break; cur = a; }
  return cur;
}

// Le bateau tient-il la TWA et la voile de l'action en cours ?
function planCheck(race, now = Date.now()) {
  const cur = currentAction(planOf(race), now);
  if (!cur) return null;
  // Le réglage de départ commence "maintenant" à chaque recalcul : pas de délai de grâce pour lui
  const fresh = cur.prev_twa != null && now - cur.t < PLAN_GRACE_MS;
  return {
    cur,
    locked: twaLocked(race.boat),
    twaOff: !fresh && Math.abs(race.boat.twa - cur.twa) > PLAN_TOL_DEG,
    sailOff: !fresh && baseSail(race.boat.sail) !== cur.sail,
  };
}

// Actions à venir pas encore cochées comme programmées
const toProgram = (race, until) => planOf(race).filter((a) => a.t > Date.now() && a.t <= until && !isDone(race.id, a.t));

// Actions cochées "programmée", par course. Clé arrondie à 20 min : une route
// recalculée décale souvent l'heure de quelques minutes, la coche doit suivre.
const doneKey = (t) => Math.round(t / (20 * 60e3));
const doneSet = (raceId) => new Set(store.get(`done-${raceId}`, []));
function setDone(raceId, t, done) {
  const set = doneSet(raceId);
  done ? set.add(doneKey(t)) : set.delete(doneKey(t));
  store.set(`done-${raceId}`, [...set]);
}
const isDone = (raceId, t) => doneSet(raceId).has(doneKey(t));

// --- État ------------------------------------------------------------------

let state = null;
let offline = false;
let selectedId = store.get("race", null);
let horizon = store.get("horizon", 12);
let rerouteFrom = null;      // computed_at de la route quand on a demandé un recalcul
let nextKey = null;          // pour ne reconstruire la carte "prochaine manœuvre" que si elle change
const notified = new Set();
const offPlanNotified = new Set();

const selectedRace = () => state?.races.find((r) => r.id === selectedId) || null;

async function refresh() {
  try {
    const res = await fetch("/api/state", { cache: "no-store" });
    state = await res.json();
    offline = false;
  } catch {
    offline = true;
  }
  render();
}

// --- Rendu -----------------------------------------------------------------

function render() {
  renderSync();
  if (!state) return;
  $("login").hidden = !state.status.needs_login;

  const races = state.races;
  $("empty").hidden = races.length > 0 || state.status.needs_login || !state.status.last_poll;
  $("dashboard").hidden = races.length === 0;
  if (!races.length) { $("race-tabs").replaceChildren(); return; }
  if (!races.some((r) => r.id === selectedId)) selectedId = races[0].id;

  renderTabs(races);
  const race = selectedRace();
  renderBanner(race);
  renderTiles(race);
  renderRouteInfo(race);
  renderPlan(race);
  nextKey = null;
  renderNext(race);
  renderMap(race);
  renderCharts(race);
}

function renderSync() {
  const box = $("sync"), text = box.querySelector(".sync-text");
  box.className = "sync";
  if (offline) { box.classList.add("err"); text.textContent = "Serveur arrêté : relance python app.py"; return; }
  if (!state) { text.textContent = "Connexion…"; return; }
  const { error, last_poll } = state.status;
  if (error) { box.classList.add("err"); text.textContent = error; return; }
  if (!last_poll) { text.textContent = "Premier relevé en cours…"; return; }
  const age = Date.now() - last_poll;
  box.classList.add(age > 3 * 60e3 ? "warn" : "ok");
  text.textContent = `Suivi actif · relevé ${ago(age)}`;
}

function renderTabs(races) {
  $("race-tabs").replaceChildren(...races.map((r) => el("button", {
    class: "race-tab", type: "button", role: "tab", "aria-selected": String(r.id === selectedId),
    onclick: () => { selectedId = r.id; store.set("race", r.id); fittedFor = null; render(); },
  }, r.name)));
}

function renderBanner(race) {
  const banner = $("banner");
  const show = (level, title, body) => {
    banner.className = `banner ${level}`;
    banner.replaceChildren(el("span", { class: "icon", "aria-hidden": "true" }, { good: "✅", critical: "⛔" }[level] || "⚠️"),
      el("div", {}, el("strong", {}, title), body));
    banner.hidden = false;
  };
  const { boat, route } = race;
  banner.hidden = true;
  if (boat.state && boat.state !== "racing") {
    return show("", "Course terminée pour ce bateau", "Le suivi continue tant que la course apparaît sur ton compte.");
  }
  const check = route?.plan && planCheck(race);
  if (!check) return;
  if (Date.now() - route.computed_at > 2 * 3600e3) {
    return show("", "Plan ancien", `Route calculée ${ago(Date.now() - route.computed_at)} : le recalcul automatique n'a pas abouti. Clique sur Recalculer.`);
  }
  const { cur } = check;
  const want = `TWA ${signedDeg(cur.twa)} ${side(cur.twa)} sous ${sailName(cur.sail)}`;
  if (check.twaOff || check.sailOff) {
    return show("critical", "Le bateau ne suit pas le plan",
      `En ce moment, le plan demande ${want}. Ton bateau est à TWA ${signedDeg(boat.twa)} sous ${sailName(baseSail(boat.sail))} : règle-le dans le jeu.`);
  }
  if (!check.locked) {
    return show("", "Le bateau est en cap fixe",
      "Le plan suppose le pilote TWA : verrouille la TWA dans le jeu pour que le bateau suive tout seul les bascules du vent.");
  }
  const until = Date.now() + 12 * 3600e3;
  const todo = toProgram(race, until).length;
  show("good", "Le bateau suit le plan", `${want} jusqu'à ${shortTime(cur.until)}. ` + (todo
    ? `${todo} action${todo > 1 ? "s" : ""} à programmer d'ici ${shortTime(until)}.`
    : "Les actions des 12 prochaines heures sont programmées."));
}

function tile(label, value, unit, sub, swatch) {
  return el("div", { class: "tile" },
    el("div", { class: "tile-label" }, label),
    el("div", { class: "tile-value" }, swatch && el("span", { class: "swatch", style: `background:${swatch}` }), value, unit && el("small", {}, unit)),
    el("div", { class: "tile-sub" }, sub || " "));
}

function renderTiles(race) {
  const b = race.boat, route = race.route;
  const target = route && routeAt(route, Date.now());
  const sail = baseSail(b.sail);
  const tiles = [
    tile("Vitesse", nf1.format(b.speed), "nds", target && `route : ${nf1.format(target.speed)} nds`),
    tile("Cap", deg(b.heading), null, `TWA ${signedDeg(b.twa)} ${side(b.twa)} · ${twaLocked(b) ? "pilote TWA" : "cap fixe"}`),
    tile("Vent", nf1.format(b.tws), "nds", `du ${deg(b.twd)}`),
    tile("Voile", sailName(sail), null, target && `route : ${sailName(target.sail)}`, sailColor(sail)),
    tile("Classement", nf0.format(b.rank), race.skippers && `/ ${nf0.format(race.skippers)}`,
      race.skippers && `top ${Math.max(1, Math.round((b.rank / race.skippers) * 100))} %`),
    tile("Énergie", nf0.format(b.stamina), "%", null),
    tile("Reste", nf0.format(b.distanceToEnd), "mn", `${nf0.format(b.distanceFromStart)} mn parcourus`),
    tile("Arrivée estimée", route ? dayTime(route.arrival) : "—", null,
      route && el("span", {}, "dans ", el("span", { "data-until": route.arrival }, countdown(route.arrival - Date.now())))),
  ];
  $("tiles").replaceChildren(...tiles);
}

function renderRouteInfo(race) {
  const info = $("route-info"), btn = $("reroute");
  const route = race.route;
  const waiting = rerouteFrom !== null;
  btn.disabled = waiting;
  btn.textContent = waiting ? "Calcul…" : "Recalculer";
  const lines = [];
  if (route) {
    const gfs = (route.gfs.match(/(\d{2})Z/) || [])[1];
    lines.push(`Météo ${gfs ? `GFS ${gfs}Z` : route.gfs} · calculée ${ago(Date.now() - route.computed_at)}. `,
      "Recalcul automatique toutes les heures depuis la position du bateau.");
  } else {
    lines.push("Calcul de la première route en cours…");
  }
  if (race.route_error) lines.push(el("span", { class: "err" }, race.route_error));
  info.replaceChildren(...lines);
}

function renderPlan(race) {
  const body = $("plan");
  const plan = planOf(race);
  const now = Date.now();
  $("horizons").replaceChildren(...HORIZONS.map(([h, label]) => el("button", {
    type: "button", class: "chip", "aria-pressed": String(h === horizon),
    onclick: () => { horizon = h; store.set("horizon", h); renderPlan(race); },
  }, label)));
  if (!plan.length) {
    body.replaceChildren(el("tr", {}, el("td", { colspan: 8, class: "sub" }, "Plan en cours de calcul…")));
    $("plan-more").textContent = "";
    return;
  }
  const cur = currentAction(plan, now);
  const limit = horizon ? now + horizon * 3600e3 : Infinity;
  const nextT = plan.find((a) => a.t > now)?.t;

  body.replaceChildren(...plan.filter((a) => a === cur || (a.t > now && a.t <= limit)).map((a) => {
    const isCur = a === cur && a.t <= now;
    const done = !isCur && isDone(race.id, a.t);
    const major = a.kinds.some((k) => MAJOR.has(k));
    return el("tr", { class: [isCur && "is-current", a.t === nextT && "is-next", done && "is-done"].filter(Boolean).join(" ") },
      el("td", {}, isCur ? "Maintenant" : shortTime(a.t)),
      el("td", { class: "sub" }, isCur ? "en cours" : el("span", { "data-until": a.t }, countdown(a.t - now))),
      el("td", { class: `kind ${major ? "kind-major" : ""}` }, a.kinds.join(" + ")),
      el("td", { class: "num strong" }, signedDeg(a.twa)),
      el("td", {}, el("span", { class: "swatch", style: `background:${sailColor(a.sail)}` }), sailName(a.sail)),
      el("td", { class: "num sub" }, `≈ ${deg(a.hdg)}`),
      el("td", { class: "num sub" }, duration(a.until - a.t)),
      el("td", { class: "center" }, !isCur && el("input", {
        type: "checkbox", checked: done, "aria-label": `Programmée : ${a.kinds.join(" + ")} ${shortTime(a.t)}`,
        onchange: (e) => { setDone(race.id, a.t, e.target.checked); renderPlan(race); renderBanner(race); nextKey = null; renderNext(race); },
      })));
  }));
  const later = plan.filter((a) => a.t > limit).length;
  $("plan-more").textContent = later ? `+ ${later} action${later > 1 ? "s" : ""} plus tard` : "Jusqu'à l'arrivée.";
}

function renderNext(race) {
  const card = $("next");
  const now = Date.now();
  const next = planOf(race).find((a) => a.t > now);
  const done = next && isDone(race.id, next.t);
  const soon = next && !done && next.t - now < SOON_MS;
  const key = `${race.id}|${race.route?.computed_at}|${next?.t}|${done}|${soon}`;
  if (key === nextKey) return;
  nextKey = key;

  card.className = `card next-card${done ? " done" : soon ? " soon" : ""}`;
  const label = el("div", { class: "next-label" }, done ? "Prochaine action · programmée" : "Prochaine action à programmer");
  if (!race.route?.plan) { card.replaceChildren(label, el("div", { class: "next-what" }, "Plan en cours de calcul…")); return; }
  if (!next) {
    card.replaceChildren(label, el("div", { class: "next-what" }, "Aucune"),
      el("div", { class: "next-detail" }, "Garde le réglage actuel jusqu'à l'arrivée."));
    return;
  }
  card.replaceChildren(
    label,
    el("div", { class: "next-countdown", "data-until": next.t }, countdown(next.t - now)),
    el("div", { class: "next-what" }, `${next.kinds.join(" + ")} · ${dayTime(next.t)}`),
    el("div", { class: "next-detail" },
      `TWA ${signedDeg(next.prev_twa)} → `, el("strong", {}, `${signedDeg(next.twa)} ${side(next.twa)}`), " · ",
      el("span", { class: "swatch", style: `background:${sailColor(next.sail)}` }), sailName(next.sail),
      ` · cap ≈ ${deg(next.hdg)} · tenue ${duration(next.until - next.t)}`),
    el("label", { class: "next-check" },
      el("input", { type: "checkbox", checked: done,
        onchange: (e) => { setDone(race.id, next.t, e.target.checked); nextKey = null; renderNext(race); renderPlan(race); renderBanner(race); } }),
      "Programmée dans le jeu"));
}

// Mise à jour à la seconde des comptes à rebours, sans reconstruire la page
function tick() {
  const now = Date.now();
  document.querySelectorAll("[data-until]").forEach((n) => { n.textContent = countdown(Number(n.dataset.until) - now); });
  renderSync();
  const race = selectedRace();
  if (race) renderNext(race);
  notifyActions(now);
}

// --- Carte -------------------------------------------------------------------

let map, tiles, fittedFor = null, mapKey = null;
const layers = {};

function initMap() {
  map = L.map("map", { zoomControl: true, attributionControl: true }).setView([50, -140], 4);
  for (const name of ["track", "route", "marks", "boat"]) layers[name] = L.layerGroup().addTo(map);
  setTiles();
}

function setTiles() {
  if (tiles) tiles.remove();
  const layer = isDark() ? "Canvas/World_Dark_Gray_Base" : "Ocean/World_Ocean_Base";
  tiles = L.tileLayer(`https://server.arcgisonline.com/ArcGIS/rest/services/${layer}/MapServer/tile/{z}/{y}/{x}`, {
    maxZoom: 13,
    attribution: "Fond de carte &copy; Esri",
  }).addTo(map);
}

// Longitudes rendues continues (pas de saut de 360° à l'antiméridien)
function unwrap(latlons, refLon) {
  let prev = refLon;
  return latlons.map(([lat, lon]) => {
    while (lon - prev > 180) lon -= 360;
    while (lon - prev < -180) lon += 360;
    prev = lon;
    return [lat, lon];
  });
}

function boatIcon(heading) {
  const color = cssVar("--text");
  const fill = cssVar("--accent");
  return L.divIcon({
    className: "boat-icon", iconSize: [30, 30], iconAnchor: [15, 15],
    html: `<svg width="30" height="30" viewBox="0 0 30 30" style="transform:rotate(${heading}deg)">
      <path d="M15 2 L23 26 L15 21 L7 26 Z" fill="${fill}" stroke="${color}" stroke-width="1.5" stroke-linejoin="round"/></svg>`,
  });
}

function renderMap(race) {
  const { boat, route } = race;
  const key = [race.id, route?.computed_at, race.track.length, boat.lastCalcDate, isDark()].join("|");
  if (key === mapKey) return;
  mapKey = key;
  Object.values(layers).forEach((g) => g.clearLayers());
  const refLon = boat.pos.lon;
  const boatLL = [boat.pos.lat, boat.pos.lon];
  const bounds = [boatLL];

  // Trace parcourue (enregistrée pendant que le suivi tourne)
  const track = unwrap([...race.track.map(([, lat, lon]) => [lat, lon]), boatLL], refLon);
  if (track.length > 1) {
    L.polyline(track, { color: cssVar("--track"), weight: 2, dashArray: "4 5", opacity: .9 }).addTo(layers.track);
  }

  const legend = [];
  if (route) {
    const pts = route.points;
    const lls = unwrap(pts.map((p) => [p.lat, p.lon]), refLon);
    bounds.push(...lls);
    // Un tronçon par voile, chaque tronçon rejoignant le suivant
    let start = 0;
    const sails = new Set();
    for (let i = 1; i <= pts.length; i++) {
      const sail = pts[start].sail;
      if (i === pts.length || (pts[i].sail && pts[i].sail !== sail)) {
        sails.add(sail);
        L.polyline(lls.slice(start, Math.min(i + 1, pts.length)), {
          color: sailColor(sail), weight: 3.5, opacity: .95, lineCap: "round", lineJoin: "round",
        }).bindTooltip(`Route · ${sailName(sail)}`, { sticky: true, className: "map-tip" }).addTo(layers.route);
        start = i;
      }
    }
    sails.forEach((s) => s && legend.push(el("span", { class: "key", style: `color:${sailColor(s)}` },
      el("i", { class: "key-line" }), el("span", { style: "color:var(--text-2)" }, sailName(s)))));

    // Repères horaires le long de la route
    const step = route.arrival - route.departure > 72 * 3600e3 ? 24 : route.arrival - route.departure > 36 * 3600e3 ? 12 : 6;
    for (let h = step; ; h += step) {
      const t = route.departure + h * 3600e3;
      if (t >= route.arrival) break;
      const i = pts.findIndex((p) => p.t >= t);
      if (i < 0) break;
      L.circleMarker(lls[i], { radius: 3, color: cssVar("--text-2"), weight: 1.5, fillColor: cssVar("--surface"), fillOpacity: 1 })
        .bindTooltip(`+${h} h`, { permanent: true, direction: "right", offset: [6, 0], className: "time-label" })
        .addTo(layers.marks);
    }

    // Actions du plan
    for (const a of route.plan || []) {
      const i = pts.findIndex((p) => p.t === a.t);
      if (i <= 0) continue;
      L.circleMarker(lls[i], { radius: 6, color: sailColor(a.sail), weight: 2.5, fillColor: cssVar("--surface"), fillOpacity: 1 })
        .bindTooltip(`<strong>${a.kinds.join(" + ")}</strong><br>${dayTime(a.t)} · TWA ${signedDeg(a.twa)} · ${sailName(a.sail)}`, { className: "map-tip" })
        .addTo(layers.marks);
    }
  }

  if (race.end) {
    const [endLL] = unwrap([[race.end.lat, race.end.lon]], refLon);
    bounds.push(endLL);
    L.marker(endLL, { icon: L.divIcon({ className: "boat-icon", html: '<span style="font-size:20px">🏁</span>', iconSize: [24, 24], iconAnchor: [5, 22] }) })
      .bindTooltip(el("span", {}, race.end.name ? `Arrivée · ${race.end.name}` : "Arrivée"), { className: "map-tip" }).addTo(layers.marks);
  }

  L.marker(boatLL, { icon: boatIcon(boat.heading), zIndexOffset: 1000 })
    .bindTooltip(`Ton bateau · ${nf1.format(boat.speed)} nds · cap ${deg(boat.heading)}`, { className: "map-tip" })
    .addTo(layers.boat);

  legend.push(el("span", { class: "key", style: `color:${cssVar("--track")}` }, el("i", { class: "key-line dashed" }), el("span", { style: "color:var(--text-2)" }, "Trace")));
  $("legend").replaceChildren(...legend);

  if (fittedFor !== race.id) {
    map.invalidateSize();  // la carte a pu être créée alors que le tableau de bord était masqué
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 9 });
    fittedFor = race.id;
  }
  $("recenter").onclick = () => map.fitBounds(bounds, { padding: [40, 40], maxZoom: 9 });
}

// --- Graphiques (SVG) -------------------------------------------------------------

const SVG_NS = "http://www.w3.org/2000/svg";
function svg(tag, attrs = {}) {
  const n = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
}
// Axe vertical : pas rond (1, 2, 5, 10…) et au plus 5 graduations
function niceScale(v) {
  const step = [1, 2, 5, 10, 20, 50].find((st) => Math.ceil((v * 1.08) / st) <= 5) || 100;
  return { max: Math.max(step, Math.ceil((v * 1.08) / step) * step), step };
}

let charts = [], chartKey = null;

function lineChart(container, pts, { value, colorOf, className }) {
  const W = container.clientWidth, H = container.clientHeight;
  const m = { l: 30, r: 8, t: 8, b: 22 };
  const t0 = pts[0].t, t1 = pts[pts.length - 1].t;
  const { max: yMax, step: yStep } = niceScale(Math.max(...pts.map(value)));
  const x = (t) => m.l + ((t - t0) / (t1 - t0 || 1)) * (W - m.l - m.r);
  const y = (v) => H - m.b - (v / yMax) * (H - m.t - m.b);
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });

  for (let v = 0; v <= yMax + 1e-9; v += yStep) {
    root.append(svg("line", { class: "gridline", x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }));
    const label = svg("text", { class: "axis-label", x: m.l - 6, y: y(v) + 4, "text-anchor": "end" });
    label.textContent = nf0.format(v);
    root.append(label);
  }
  // Graduations : chaque jour à minuit (nom du jour) et midi
  const d = new Date(t0); d.setMinutes(0, 0, 0); d.setHours(d.getHours() < 12 ? 12 : 24);
  for (let t = d.getTime(); t < t1; t += 12 * 3600e3) {
    const midnight = new Date(t).getHours() === 0;
    const label = svg("text", { class: "axis-label", x: x(t), y: H - 6, "text-anchor": "middle" });
    label.textContent = midnight ? dfDay.format(t).replace(".", "") : "12h";
    root.append(label);
    if (midnight) root.append(svg("line", { class: "gridline", x1: x(t), x2: x(t), y1: m.t, y2: H - m.b }));
  }

  // Courbe, découpée en tronçons de même couleur
  let start = 0;
  for (let i = 1; i <= pts.length; i++) {
    if (i === pts.length || colorOf(pts[i]) !== colorOf(pts[start])) {
      const seg = pts.slice(start, Math.min(i + 1, pts.length));
      root.append(svg("path", {
        d: seg.map((p, j) => `${j ? "L" : "M"}${x(p.t).toFixed(1)},${y(value(p)).toFixed(1)}`).join(""),
        fill: "none", stroke: colorOf(pts[start]) || "currentColor", "stroke-width": 2,
        "stroke-linejoin": "round", "stroke-linecap": "round", class: className || "",
      }));
      start = i;
    }
  }

  const cross = svg("line", { class: "crosshair", y1: m.t, y2: H - m.b, visibility: "hidden" });
  const dot = svg("circle", { class: "hover-dot", r: 4, visibility: "hidden" });
  const hit = svg("rect", { x: m.l, y: 0, width: W - m.l - m.r, height: H, fill: "transparent" });
  root.append(cross, dot, hit);
  container.replaceChildren(root);

  const nearest = (clientX) => {
    const box = root.getBoundingClientRect();
    const t = t0 + ((clientX - box.left - m.l) / (W - m.l - m.r)) * (t1 - t0);
    let best = 0;
    pts.forEach((p, i) => { if (Math.abs(p.t - t) < Math.abs(pts[best].t - t)) best = i; });
    return best;
  };
  hit.addEventListener("pointermove", (e) => showHover(nearest(e.clientX), e.clientX, e.clientY));
  hit.addEventListener("pointerleave", hideHover);

  return {
    show(i) {
      const p = pts[i];
      cross.setAttribute("x1", x(p.t)); cross.setAttribute("x2", x(p.t)); cross.setAttribute("visibility", "visible");
      dot.setAttribute("cx", x(p.t)); dot.setAttribute("cy", y(value(p)));
      dot.setAttribute("fill", colorOf(p) || cssVar("--text-2")); dot.setAttribute("visibility", "visible");
    },
    hide() { cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); },
  };
}

let hoverPts = [];
function showHover(i, cx, cy) {
  charts.forEach((c) => c.show(i));
  const p = hoverPts[i];
  const row = (color, label, value) => el("div", { class: "tt-row" },
    el("span", {}, color && el("i", { class: "key-line", style: `color:${color};width:12px` }), label), el("strong", {}, value));
  const tip = $("tooltip");
  tip.replaceChildren(
    el("div", { class: "tt-time" }, dayTime(p.t)),
    row(sailColor(p.sail), "Vitesse", `${nf1.format(p.speed)} nds`),
    row(cssVar("--text-2"), "Vent", `${nf1.format(p.tws)} nds`),
    row(null, "Cap", deg(p.hdg)),
    row(null, "TWA", signedDeg(p.twa)),
    row(null, "Voile", sailName(p.sail)));
  tip.hidden = false;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  tip.style.left = `${Math.min(cx + 14, innerWidth - w - 8)}px`;
  tip.style.top = `${Math.max(8, cy - h - 12)}px`;
}
function hideHover() { charts.forEach((c) => c.hide()); $("tooltip").hidden = true; }

function renderCharts(race, force = false) {
  const route = race.route;
  const key = [race.id, route?.computed_at, isDark(), $("chart-speed").clientWidth].join("|");
  if (!force && key === chartKey) return;
  chartKey = key;
  if (!route) { charts = []; $("chart-speed").replaceChildren(); $("chart-wind").replaceChildren(); return; }
  hoverPts = route.points.filter((p) => !p.end && p.t >= Date.now() - 10 * 60e3);
  if (hoverPts.length < 2) hoverPts = route.points.filter((p) => !p.end);
  charts = [
    lineChart($("chart-speed"), hoverPts, { value: (p) => p.speed, colorOf: (p) => sailColor(p.sail) }),
    lineChart($("chart-wind"), hoverPts, { value: (p) => p.tws, colorOf: () => cssVar("--text-2"), className: "series-wind" }),
  ];
  const sails = [...new Set(hoverPts.map((p) => p.sail))];
  $("speed-legend").replaceChildren(...(sails.length > 1 ? sails.map((s) => el("span", { class: "key", style: `color:${sailColor(s)}` },
    el("i", { class: "key-line" }), el("span", { style: "color:var(--text-2)" }, sailName(s)))) : []));
}

// --- Alertes ---------------------------------------------------------------

const canNotify = "Notification" in window;
let notifyOn = canNotify && store.get("notify", false) && Notification.permission === "granted";

function renderNotifyBtn() {
  const btn = $("notify-btn");
  btn.hidden = !canNotify;
  btn.setAttribute("aria-pressed", String(notifyOn));
  btn.textContent = notifyOn ? "🔔 Alertes activées" : "🔕 Alertes";
  btn.title = "Notification 10 min avant chaque manœuvre non programmée";
}

function notifyActions(now) {
  if (!notifyOn || !state) return;
  for (const race of state.races) {
    for (const a of planOf(race)) {
      const key = `${race.id}|${doneKey(a.t)}`;
      const left = a.t - now;
      if (left <= 0 || left > ALERT_BEFORE_MS || notified.has(key) || isDone(race.id, a.t)) continue;
      notified.add(key);
      new Notification(`${a.kinds.join(" + ")} dans ${countdown(left)}`, {
        body: `${race.name} · ${dfTime.format(a.t)} · TWA ${signedDeg(a.twa)} · ${sailName(a.sail)}`, tag: key,
      });
    }
    // Une seule notification par écart au plan (par action en cours)
    const check = race.route?.plan && planCheck(race, now);
    if (check && (check.twaOff || check.sailOff)) {
      const key = `off|${race.id}|${check.cur.t}`;
      if (offPlanNotified.has(key)) continue;
      offPlanNotified.add(key);
      new Notification("Le bateau ne suit pas le plan", {
        body: `${race.name} : TWA ${signedDeg(race.boat.twa)} au lieu de ${signedDeg(check.cur.twa)} (${sailName(check.cur.sail)})`, tag: key,
      });
    }
  }
}

// --- Actions ---------------------------------------------------------------

$("notify-btn").addEventListener("click", async () => {
  if (!notifyOn && Notification.permission !== "granted") {
    if (await Notification.requestPermission() !== "granted") return;
  }
  notifyOn = !notifyOn;
  store.set("notify", notifyOn);
  renderNotifyBtn();
});

$("reroute").addEventListener("click", async () => {
  const race = selectedRace();
  if (!race) return;
  rerouteFrom = race.route?.computed_at ?? 0;
  renderRouteInfo(race);
  await fetch(`/api/races/${race.id}/reroute`, { method: "POST" }).catch(() => {});
  const started = Date.now();
  while (Date.now() - started < 90e3) {
    await new Promise((r) => setTimeout(r, 2000));
    await refresh();
    const r = selectedRace();
    if (!r || (r.route?.computed_at ?? 0) !== rerouteFrom || r.route_error) break;
  }
  rerouteFrom = null;
  if (selectedRace()) renderRouteInfo(selectedRace());
});


$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  const err = $("login-error");
  err.hidden = true;
  try {
    const res = await fetch("/api/login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mail: form.get("mail"), mdp: form.get("mdp") }),
    });
    const data = await res.json();
    if (!data.ok) { err.textContent = data.error; err.hidden = false; return; }
    $("login").hidden = true;
    refresh();
  } catch {
    err.textContent = "Serveur injoignable."; err.hidden = false;
  }
});

matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  setTiles(); mapKey = null; chartKey = null; render();
});
let resizeTimer;
addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { const r = selectedRace(); if (r) renderCharts(r); }, 150);
});

// --- Démarrage -------------------------------------------------------------

initMap();
renderNotifyBtn();
refresh();
setInterval(refresh, POLL_MS);
setInterval(tick, 1000);

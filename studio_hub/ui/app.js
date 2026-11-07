"use strict";

const $ = (sel) => document.querySelector(sel);
const S = { data: null, view: "all", chip: null, query: "", selected: null, gridSig: "", wasCapturing: false, recording: false, versions: {} };

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

// Polling must not rebuild unchanged DOM: that drops clicks and keyboard focus.
function setHtml(el, html) {
  if (el._html !== html) { el.innerHTML = html; el._html = html; }
}

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

/* ---------- data helpers ---------- */

const cats = () => S.data.categories.filter((c) => !K.deleting.has(c.key));  // K: categories.js
const catOf = (key) => cats().find((c) => c.key === key) || cats()[cats().length - 1];
const pluginById = (id) => S.data.plugins.find((p) => p.id === id);
const hasPicture = (p) => p.capture === "ok" || p.capture === "custom";

const devOf = (p) => p.developer || "Unknown developer";

function inView(p, view) {
  if (view === "all") return true;
  if (view === "chains") return false;
  if (view === "favourites") return p.favourite;
  if (view === "recent") return p.last_used > 0;
  if (view.startsWith("dev:")) return devOf(p) === view.slice(4);
  return p.category === view.slice(4);
}

// In a category, chips narrow by developer; everywhere else they have chips (a developer, Favourites,
// Recently used) they narrow by category.
const chipsByCategory = () => !S.view.startsWith("cat:");

function chipMatches(p) {
  if (!S.chip) return true;
  return chipsByCategory() ? p.category === S.chip : devOf(p) === S.chip;
}

function chipOptions() {
  if (S.view === "all" || S.view === "chains") return [];  // the sidebar already lists every category
  const byDev = chipsByCategory();
  const counts = new Map();
  for (const p of S.data.plugins.filter((x) => inView(x, S.view))) {
    const key = byDev ? p.category : devOf(p);
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  const options = [...counts].map(([key, n]) => ({ key, n, label: byDev ? catOf(key).label : key }));
  return byDev
    ? options.sort((a, b) => cats().findIndex((c) => c.key === a.key) - cats().findIndex((c) => c.key === b.key))
    : options.sort((a, b) => b.n - a.n || a.label.localeCompare(b.label));
}

function developers() {
  const counts = new Map();
  for (const p of S.data.plugins) counts.set(devOf(p), (counts.get(devOf(p)) || 0) + 1);
  return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function visiblePlugins() {
  const words = S.query.toLowerCase().split(/\s+/).filter(Boolean);
  let list = S.data.plugins.filter((p) => inView(p, S.view) && chipMatches(p));
  if (words.length) {
    list = list.filter((p) => {
      const hay = `${p.name} ${devOf(p)} ${catOf(p.category).label} ${p.variants.map((v) => v.label).join(" ")}`.toLowerCase();
      return words.every((w) => hay.includes(w));
    });
  }
  if (S.view === "recent") list = list.sort((a, b) => b.last_used - a.last_used).slice(0, 30);
  return list;
}

function viewTitle() {
  if (S.view === "all") return "All plugins";
  if (S.view === "favourites") return "Favourites";
  if (S.view === "recent") return "Recently used";
  if (S.view === "chains") return "Chains";
  if (S.view.startsWith("dev:")) return S.view.slice(4);
  return catOf(S.view.slice(4)).label;
}

function initials(name) {
  const words = name.replace(/[^\p{L}\p{N} ]/gu, " ").split(/\s+/).filter(Boolean);
  return (words.length > 1 ? words[0][0] + words[1][0] : name.slice(0, 2)).toUpperCase();
}

const CAPTION = { failed: "Couldn't capture", crashed: "Crashed when opened" };
const DETAIL_CAPTION = {
  failed: "Couldn't capture this plugin",
  crashed: "This plugin crashed or froze when it was opened, so it's skipped. Retake to try again.",
};

const shotUrl = (p) => `/snapshots/${p.shot_id || p.id}.png?v=${p.shot || 0}`;
// The version "Add to track" uses: the one picked in the details, else the one usually added.
const versionOf = (p) => (p.variants.some((v) => v.id === S.versions[p.id]) ? S.versions[p.id] : p.preferred);
const versionLabel = (p) => p.variants.find((v) => v.id === versionOf(p))?.label;
// The picked version's own picture when it has one (a Mono version can look different), else the main one.
function pictureOf(p) {
  const own = p.variants.find((v) => v.id === versionOf(p) && v.shot);
  return { url: own ? `/snapshots/${own.id}.png?v=${own.shot}` : shotUrl(p), has: Boolean(own) || hasPicture(p), own };
}
// Stereo / Mono / Sidechain under a card: pick the version, then double-click the card as usual.
const versionSwitch = (p, cls = "") => `<span class="seg version-switch ${cls}" role="radiogroup" aria-label="Version of ${esc(p.name)}">${
  p.variants.map((v) => `<button role="radio" data-version="${v.id}" data-for="${p.id}" aria-checked="${v.id === versionOf(p)}" aria-selected="${v.id === versionOf(p)}">${esc(v.label)}</button>`).join("")}</span>`;

/* ---------- page help ---------- */

const HELP = {
  library: "All the plugins REAPER has found on your computer, each with a picture. Double-click one to put it on the selected track. Drag a card onto a category to move it.",
  favourites: "Plugins you've starred. Select one and press F to star or unstar it. The chips narrow it down by category.",
  recent: "The last plugins you added from Ordel, newest first.",
  chains: "Save a chain from the selected REAPER track. Click a chain to put it on the selected track, or use its edit button to change it. Turn on 'Use as return track' to make it a send.",
  settings: "Themes, your shortcut, pictures and the REAPER connection. New plugin not showing? Restart REAPER so it scans it, then refresh.",
};
const helpKey = () => (["favourites", "recent", "chains"].includes(S.view) ? S.view : "library");
const helpButton = (key) => `<span class="help"><button class="help-btn" aria-label="About this page" aria-describedby="help-${key}">${icon("help")}</button><span class="help-pop" role="tooltip" id="help-${key}">${esc(HELP[key])}</span></span>`;

/* ---------- rendering ---------- */

function render() {
  if (!S.data) return;
  const st = S.data.settings;
  Object.assign(document.body.dataset, {
    theme: st.theme, accent: st.accent, fit: st.picture_fit, density: st.density, corners: st.corners,
    developer: st.show_developer ? "on" : "off", page: S.view === "chains" ? "chains" : "plugins",
  });
  const viewCat = S.view.startsWith("cat:") ? catOf(S.view.slice(4)).color : "#5e5ce6";
  document.documentElement.style.setProperty("--cat", viewCat);
  document.documentElement.style.setProperty("--tile", `${S.data.settings.tile_size}px`);
  renderSidebar();
  renderToolbar();
  renderBanners();
  renderChainTools();
  renderGrid();
  renderDetail();
}

function navItem(view, label, n, lead) {
  const current = S.view === view ? ' aria-current="true"' : "";
  return `<button class="nav-item" data-view="${view}"${current}>${lead}<span class="label">${esc(label)}</span><span class="n">${n}</span></button>`;
}

function renderSidebar() {
  const ps = S.data.plugins;
  setHtml($("#nav-library"),
    navItem("all", "All plugins", ps.length, icon("grid")) +
    navItem("favourites", "Favourites", ps.filter((p) => p.favourite).length, icon("star")) +
    navItem("recent", "Recently used", Math.min(30, ps.filter((p) => p.last_used > 0).length), icon("clock")) +
    navItem("chains", "Chains", chains().filter((c) => !c.hidden).length, icon("chain")));
  const mode = S.data.settings.sidebar_mode;
  document.querySelectorAll("#nav-switch [data-mode]").forEach((b) => b.setAttribute("aria-selected", b.dataset.mode === mode));
  setHtml($("#nav-categories"), mode === "developers"
    ? developers().map(([name, n]) => navItem(`dev:${name}`, name, n, `<span class="initial">${esc(name[0].toUpperCase())}</span>`)).join("")
    : cats()
      .map((c) => ({ c, n: ps.filter((p) => p.category === c.key).length }))
      .filter(({ c, n }) => n > 0 || c.custom || S.view === `cat:${c.key}`)  // yours show even when empty
      .map(({ c, n }) => navItem(`cat:${c.key}`, c.label, n,
        `<span class="tag${c.key === "uncategorised" ? " uncat" : ""}" style="--c:${c.color}"></span>`))
      .join("") + newCategoryRow());

  const r = S.data.reaper;
  setHtml($("#reaper-status"), `<span class="dot${r.connected ? " on" : ""}"></span>${r.connected ? "REAPER connected" : "REAPER not connected"}`);
  $("#reaper-status").title = r.connected ? "Plugins you add go to the selected track" : "Connect REAPER";
}

function renderToolbar() {
  const n = visiblePlugins().length;
  const total = S.data.plugins.filter((p) => inView(p, S.view)).length;
  $("#view-title").textContent = viewTitle();
  setHtml($("#view-help"), helpButton(helpKey()) + editCategoryButton());
  $("#view-count").textContent = S.view === "chains" ? plural(visibleChains().length, "chain")
    : S.chip && !S.query ? `${n} of ${plural(total, "plugin")}` : plural(n, "plugin");
  renderChips(total);
  if (document.activeElement !== $("#tile-size")) $("#tile-size").value = S.data.settings.tile_size;  // not mid-drag
}

function renderChips(total) {
  const options = chipOptions();
  const el = $("#chips");
  el.hidden = options.length < 2;  // nothing to narrow down to
  if (el.hidden) return;
  const byDev = chipsByCategory();
  const chip = (key, label, n, lead = "") =>
    `<button class="chip" data-chip="${esc(key)}" aria-pressed="${(S.chip || "") === key}">${lead}${esc(label)} <b>${n}</b></button>`;
  setHtml(el, chip("", "All", total) + options.map((o) =>
    chip(o.key, o.label, o.n, byDev ? `<span class="tag" style="--c:${catOf(o.key).color}"></span>` : "")).join(""));
}

function renderBanners() {
  const cap = S.data.capture;
  const bar = $("#capture-bar");
  if (cap.running) {
    const pct = cap.total ? Math.round((cap.done / cap.total) * 100) : 0;
    bar.hidden = false;
    setHtml(bar, `
      <div class="what">
        <div class="line">${cap.paused ? "Capture paused" : cap.waiting ? "Waiting for REAPER to stop playing" : "Capturing pictures"}<span>${cap.done} of ${cap.total}${cap.current && !cap.paused && !cap.waiting ? `, now ${esc(cap.current)}` : ""}</span></div>
        <div class="progress"><i style="width:${pct}%"></i></div>
      </div>
      <button class="btn" data-capture="${cap.paused ? "resume" : "pause"}">${icon(cap.paused ? "play" : "pause")}${cap.paused ? "Resume" : "Pause"}</button>
      <button class="btn quiet" data-capture="cancel">Stop</button>`);
  } else {
    bar.hidden = true;
  }

  const fresh = S.data.new_plugins || [];
  const notice = $("#notice");
  notice.hidden = !fresh.length || cap.running;
  if (!notice.hidden) {
    setHtml(notice, `<span>${plural(fresh.length, "new plugin")} found</span><span class="dot-sep">·</span>
      <button class="link" data-action="capture-new">Capture ${fresh.length === 1 ? "its picture" : "pictures"}</button>
      <button class="icon-btn" data-action="dismiss-new" aria-label="Dismiss" title="Dismiss">${icon("close")}</button>`);
  }

  const r = S.data.reaper;
  const banner = $("#banner");
  if (r.library_found && !r.connected) {
    banner.hidden = false;
    setHtml(banner, `${icon("plug")}
      <div class="msg">REAPER isn't connected. <span>${r.installed ? "Open REAPER to add plugins to tracks." : "Connect it to add plugins to tracks and capture pictures."}</span></div>
      <button class="btn" data-action="connect">${r.installed ? "Reconnect" : "Connect REAPER"}</button>`);
  } else {
    banner.hidden = true;
  }
}

function emptyState() {
  if (!S.data.reaper.library_found) {
    return `<div class="glyph">${icon("plug")}</div><h2>No plugins found</h2>
      <p>Ordel reads the plugin list REAPER builds when it scans. Open REAPER, run a plugin scan in Preferences, then refresh.</p>
      <button class="btn" data-action="refresh">${icon("refresh")}Refresh</button>`;
  }
  if (S.query) {
    return `<div class="glyph">${icon("search")}</div><h2>No results for “${esc(S.query)}”</h2>
      <p>Try a shorter name or the maker. Search looks in ${esc(viewTitle().toLowerCase())}.</p>
      ${S.view !== "all" ? '<button class="btn" data-action="search-all">Search all plugins</button>' : ""}`;
  }
  if (S.view === "favourites") {
    return `<div class="glyph">${icon("star")}</div><h2>No favourites yet</h2>
      <p>Select a plugin and press F, or use the star in its details, to keep it here.</p>`;
  }
  if (S.view === "recent") {
    return `<div class="glyph">${icon("clock")}</div><h2>Nothing used yet</h2>
      <p>Plugins you add to a track from Ordel show up here.</p>`;
  }
  return `<div class="glyph">${icon("grid")}</div><h2>This category is empty</h2>
    <p>Drag a plugin onto a category in the sidebar to move it.</p>`;
}

function cardHtml(p) {
  const c = catOf(p.category);
  const sel = p.id === S.selected ? "true" : "false";
  const pic = pictureOf(p);
  const art = pic.has
    ? `<img class="bg" src="${pic.url}" alt="" loading="lazy" decoding="async"><img class="fg" src="${pic.url}" alt="" loading="lazy" decoding="async">`
    : `<div class="ph"><span class="initials">${esc(initials(p.name))}</span>${CAPTION[p.capture] ? `<span class="why">${CAPTION[p.capture]}</span>` : ""}</div>`;
  return `<li><button class="card" data-id="${p.id}" aria-selected="${sel}" draggable="true" title="${esc(p.name)}">
    <div class="art" style="--c:${c.color}">${art}${p.favourite ? `<span class="fav">${icon("star")}</span>` : ""}</div>
    <div class="meta"><span class="name">${esc(p.name)}</span>
      <span class="sub"><span class="tag" style="--c:${c.color}"></span><span class="vendor">${esc(devOf(p))}</span>${p.format !== "VST3" ? `<span class="fmt">${p.format}</span>` : ""}</span>
    </div></button>
    <button class="card-add" data-add="${p.id}" aria-label="Add ${esc(p.name)} to track" title="Add to track">${icon("plus")}</button>${p.variants.length ? versionSwitch(p, "on-card") : ""}</li>`;
}

function renderGrid() {
  if (S.view === "chains") return renderChains();
  $("#grid").classList.remove("chain-grid");
  const list = visiblePlugins();
  const sig = S.view + "|" + S.chip + "|" + S.query + "|" + list.map((p) => `${p.id}${p.capture}${p.shot || 0}${p.favourite ? 1 : 0}${p.category}${versionOf(p)}`).join(",");
  if (sig !== S.gridSig) {
    const focused = document.activeElement?.dataset?.id;
    $("#grid").innerHTML = list.map(cardHtml).join("");
    S.gridSig = sig;
    if (focused) document.querySelector(`.card[data-id="${focused}"]`)?.focus({ preventScroll: true });
  } else {
    document.querySelectorAll(".card").forEach((el) => el.setAttribute("aria-selected", el.dataset.id === S.selected));
  }
  $("#empty").hidden = list.length > 0;
  if (!list.length) $("#empty").innerHTML = emptyState();
}

function renderDetail() {
  if (S.view === "chains") return renderChainDetail();
  const panel = $("#detail");
  const p = S.selected && pluginById(S.selected);
  if (!p) { panel.hidden = true; panel.dataset.id = ""; return; }
  const c = catOf(p.category);
  const sig = JSON.stringify(p) + S.data.reaper.connected + S.data.capture.running + versionOf(p);
  if (!panel.hidden && panel.dataset.sig === sig) return;
  panel.hidden = false;
  panel.dataset.id = p.id;
  panel.dataset.sig = sig;
  const formats = [p.format, ...p.alternates.map((a) => a.split(":")[0].replace(/i$/, ""))];
  const { url, own, has } = pictureOf(p);
  const art = has
    ? `<img class="bg" src="${url}" alt=""><img class="fg" src="${url}" alt="Interface of ${esc(p.name)}">`
    : `<div class="ph"><span class="initials" style="font-size:48px">${esc(initials(p.name))}</span><span class="why">${DETAIL_CAPTION[p.capture] || "No picture yet"}</span></div>`;
  panel.innerHTML = `
    <div class="detail-head"><button class="icon-btn" data-action="close-detail" aria-label="Close details">${icon("close")}</button></div>
    <div class="detail-body">
      <div class="art" style="--c:${c.color}">${art}</div>
      <div><h2>${esc(p.name)}</h2><div class="vendor-line">${esc(devOf(p))}</div></div>
      ${p.variants.length ? `<div class="version-pick"><span class="k">Version</span>${versionSwitch(p)}</div>` : ""}
      <div class="actions">
        <button class="btn primary" data-action="send">${icon("plus")}${p.variants.length ? `Add ${esc(versionLabel(p))} to track` : "Add to track"}</button>
        <button class="btn fav-btn" data-action="favourite" aria-pressed="${p.favourite}" aria-label="Favourite" title="Favourite (F)">${icon("star")}</button>
      </div>
      <div class="fields">
        <div class="field"><span class="k">Category</span>
          <button class="cat-pick" id="category-button" aria-haspopup="listbox" aria-expanded="false" aria-label="Category: ${esc(c.label)}"><span class="tag${c.key === "uncategorised" ? " uncat" : ""}" style="--c:${c.color}"></span><span class="cat-pick-label">${esc(c.label)}</span><span class="chev"></span></button></div>
        ${p.category !== p.category_auto ? `<div class="field"><span class="k">Detected as ${esc(catOf(p.category_auto).label)}</span><button class="link" data-action="reset-category">Use detected</button></div>` : ""}
        <div class="field"><span class="k">Format</span><span class="v">${formats.join(", ")}${p.instrument ? " instrument" : ""}</span></div>
      </div>
      <div class="picture-actions">
        <button class="btn quiet" data-action="retake" ${S.data.reaper.connected && !S.data.capture.running ? "" : "disabled"}>${icon("camera")}${(p.variants.length ? own : hasPicture(p)) ? "Retake picture" : "Capture picture"}</button>
        <button class="btn quiet" data-action="custom-image">${icon("image")}Use my own image…</button>
      </div>
    </div>`;
}

/* ---------- sheets ---------- */

function openSheet(html) {
  $("#sheet").innerHTML = html;
  $("#sheet-backdrop").hidden = false;
  ($("#sheet [data-autofocus]") || $("#sheet button"))?.focus();
}
function closeSheet() {
  if (S.data && !S.data.settings.onboarded && $("#sheet").dataset.kind === "welcome") return;
  $("#sheet-backdrop").hidden = true;
  $("#sheet").dataset.kind = "";
  S.recording = false;
}

const ACCENTS = [["theme", "Theme default", null], ["brass", "Brass", "#C9A15A"], ["blue", "Blue", "#0A84FF"],
  ["green", "Green", "#30D158"], ["orange", "Orange", "#FF9F0A"], ["pink", "Pink", "#FF375F"], ["purple", "Purple", "#BF5AF2"]];
const THEME_ACCENT = { ordel: "#C9A15A", graphite: "#0A84FF", light: "#007AFF", glass: "#0A84FF" };
const APPEARANCE_DEFAULTS = { theme: "ordel", accent: "theme", picture_fit: "contain", density: "comfortable",
  corners: "rounded", show_developer: true, tile_size: 240 };

function settingsHtml() {
  const s = S.data.settings;
  const r = S.data.reaper;
  const theme = (key, label) => `<button class="theme-opt" data-theme-opt="${key}" aria-pressed="${s.theme === key}">
    <span class="swatch sw-${key}"><b></b><span><i></i><i></i><i></i><i></i></span></span>${label}</button>`;
  const choice = (label, hint, key, options) => `<div class="row"><span class="k">${label}<small>${hint}</small></span>
    <span class="seg" role="radiogroup" aria-label="${label}">${options.map(([value, text]) =>
      `<button role="radio" data-setting="${key}" data-value="${value}" aria-selected="${s[key] === value}" aria-checked="${s[key] === value}">${text}</button>`).join("")}</span></div>`;
  const missing = S.data.plugins.filter((p) => !hasPicture(p)).length;
  return `
    <div class="sheet-head"><h2 id="sheet-title">Settings ${helpButton("settings")}</h2><button class="icon-btn" data-action="close-sheet" aria-label="Close">${icon("close")}</button></div>
    <div class="sheet-body">
      <div class="sheet-section"><h3>Appearance</h3>
        <div class="themes">${theme("ordel", "Ordel")}${theme("graphite", "Graphite")}${theme("light", "Light")}${theme("glass", "Glass")}</div>
        <div class="row" style="margin-top:12px"><span class="k">Accent colour<small>Selections, chips and main buttons</small></span>
          <span class="accents">${ACCENTS.map(([key, label, colour]) => `<button class="accent-opt" data-setting="accent" data-value="${key}" aria-pressed="${s.accent === key}" title="${label}" aria-label="${label} accent" style="background:${key === "theme" ? `linear-gradient(135deg, ${THEME_ACCENT[s.theme]} 50%, var(--surface-2) 50%)` : colour}"></button>`).join("")}</span></div>
        ${choice("Pictures", "Fit shows the whole plugin; Fill crops to the card", "picture_fit", [["contain", "Fit"], ["cover", "Fill"]])}
        ${choice("Density", "Compact fits more plugins on screen", "density", [["comfortable", "Comfortable"], ["compact", "Compact"]])}
        ${choice("Corners", "Softer or sharper edges throughout", "corners", [["rounded", "Rounded"], ["square", "Square"]])}
        <div class="row"><label class="k" for="show-developer">Developer names<small>Show who makes each plugin under its name</small></label>
          <input type="checkbox" class="switch" id="show-developer" ${s.show_developer ? "checked" : ""}></div>
        <div class="row"><span class="k">Reset appearance<small>Back to the Ordel theme and default layout</small></span>
          <button class="btn quiet" data-action="reset-appearance">Reset</button></div>
      </div>
      <div class="sheet-section">
        <div class="row"><span class="k">Show Ordel<small>Works from any app, including REAPER</small></span>
          <span style="display:flex;flex-direction:column;align-items:flex-end;gap:4px"><button class="keycap" id="hotkey" data-autofocus>${esc(s.hotkey)}</button><span class="hint-error" id="hotkey-error" ${S.data.hotkey_ok ? "hidden" : ""}>Shortcut unavailable. Another app is using it.</span></span></div>
        <div class="row"><label class="k" for="hide-after-add">Hide after adding a plugin<small>Go straight back to your mix</small></label>
          <input type="checkbox" class="switch" id="hide-after-add" ${s.hide_after_add ? "checked" : ""}></div>
      </div>
      <div class="sheet-section"><h3>REAPER</h3>
        <div class="row"><span class="k">${r.connected ? "Connected" : "Not connected"}<small>${r.connected ? "Plugins are added to the selected track" : r.installed ? "Open REAPER, or reconnect" : "Connect to add plugins and capture pictures"}</small></span>
          <button class="btn" data-action="connect">${r.installed ? "Reconnect" : "Connect"}</button></div>
        <div class="row"><span class="k">Plugin list<small>${plural(S.data.plugins.length, "plugin")} from REAPER's last scan</small></span>
          <button class="btn" data-action="refresh">${icon("refresh")}Refresh</button></div>
      </div>
      <div class="sheet-section"><h3>Pictures</h3>
        <div class="row"><span class="k">${missing ? `${plural(missing, "plugin")} without a picture` : "Every plugin has a picture"}<small>Each plugin is opened once and photographed. Your project isn't touched.</small></span>
          <span style="display:flex;gap:8px">
            ${missing ? `<button class="btn" data-action="capture-missing" ${r.connected ? "" : "disabled"}>Capture missing</button>` : ""}
            <button class="btn quiet" data-action="recapture-all" ${r.connected ? "" : "disabled"}>Recapture all</button></span></div>
      </div>
    </div>
    <div class="sheet-foot"><button class="btn quiet" data-action="replay-tour">Show the tour</button><button class="btn quiet" data-action="quit">Quit Ordel</button></div>`;
}

function welcomeHtml() {
  const r = S.data.reaper;
  const cap = S.data.capture;
  const n = S.data.plugins.length;
  const pictures = S.data.plugins.filter(hasPicture).length;
  const minutes = Math.max(1, Math.round((n * 4) / 60));
  const step = (done, title, sub, action) => `<div class="step"><span class="state${done ? " done" : ""}">${done ? icon("check") : ""}</span>
    <span class="k">${title}<small>${sub}</small></span>${action}</div>`;
  let captureAction = `<button class="btn" data-action="capture-missing" ${r.connected ? "" : "disabled"}>Start</button>`;
  if (cap.running) captureAction = `<span class="count">${cap.done} of ${cap.total}</span>`;
  return `
    <div class="sheet-head"><h2 id="sheet-title">Welcome to Ordel</h2></div>
    <div class="sheet-body">
      <p class="lede">See every plugin you own as a picture of its interface, find it by sight, and send it straight to a track in REAPER.</p>
      <div class="steps">
        ${step(n > 0, n > 0 ? `Found ${plural(n, "plugin")}` : "No plugins found", n > 0 ? "Read from REAPER's plugin scan" : "Open REAPER and scan your plugins first", n > 0 ? "" : '<button class="btn" data-action="refresh">Refresh</button>')}
        ${step(r.connected, "Connect REAPER", r.connected ? "Connected" : "Adds a small script to REAPER so Ordel can add plugins to tracks", r.connected ? "" : '<button class="btn primary" data-action="connect">Connect</button>')}
        ${step(pictures > 0 && !cap.running, "Capture pictures", cap.running ? `Now ${esc(cap.current || "starting")}. You can keep using Ordel.` : `Opens each plugin once and photographs it. About ${minutes} min.`, pictures > 0 && !cap.running ? "" : captureAction)}
      </div>
    </div>
    <div class="sheet-foot"><button class="btn ${pictures > 0 || cap.running ? "primary" : "quiet"}" data-action="finish-welcome">${pictures > 0 || cap.running ? "Done" : "Skip for now"}</button></div>`;
}

function refreshSheet() {
  const kind = $("#sheet").dataset.kind;
  if ($("#sheet-backdrop").hidden || S.recording) return;
  const html = kind === "settings" ? settingsHtml() : kind === "welcome" ? welcomeHtml() : null;
  if (html && $("#sheet").dataset.sig !== html) {
    const focusedAction = document.activeElement?.dataset?.action;
    $("#sheet").innerHTML = html;
    $("#sheet").dataset.sig = html;
    if (focusedAction) $(`#sheet [data-action="${focusedAction}"]`)?.focus();
  }
}
function showSheet(kind) {
  $("#sheet").dataset.kind = kind;
  const html = kind === "settings" ? settingsHtml() : welcomeHtml();
  $("#sheet").dataset.sig = html;
  openSheet(html);
}

/* ---------- toasts ---------- */

function toast(text, warn = false, ms = 2600, action = null) {
  const el = document.createElement("div");
  el.className = `toast${warn ? " warn" : ""}${action ? " has-action" : ""}`;
  el.innerHTML = `${icon(warn ? "alert" : "check")}<span>${esc(text)}</span>`;
  if (action) {
    const b = document.createElement("button");
    b.className = "toast-action";
    b.textContent = action.label;
    b.addEventListener("click", () => { action.run(); el.remove(); });
    el.append(b);
  }
  $("#toasts").append(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 300); }, ms);
}

const SEND_ERRORS = {
  NO_TRACK: "Select a track in REAPER first",
  not_connected: "REAPER isn't connected",
  NOT_FOUND: "REAPER couldn't load this plugin",
  timeout: "REAPER didn't respond. Is a dialog open?",
};

/* ---------- actions ---------- */

async function load() {
  try {
    S.data = await api("/api/state");
  } catch {
    return;
  }
  const cap = S.data.capture;
  if (S.wasCapturing && !cap.running) {
    if (cap.crashed) toast(`REAPER closed while opening ${cap.crashed}. Reopen REAPER, then press Capture missing to finish the rest. ${cap.crashed} will be skipped.`, true, 12000);
    else if (cap.error === "BUSY") toast("Stop playback in REAPER, then capture again", true);
    else if (cap.needs_save) toast(`Save your project in REAPER, then press Capture missing for ${plural(cap.needs_save, "more plugin")}. Those can't be opened apart from REAPER, so Ordel only opens them once your work is saved.`, true, 12000);
    else if (cap.needs_reaper) toast(`${plural(cap.needs_reaper, "plugin")} ${cap.needs_reaper === 1 ? "needs" : "need"} REAPER open to capture. Open REAPER and capture again.`, true);
    else if (cap.error === "not_connected") toast("Capture stopped: REAPER disconnected", true);
    else if (cap.error) toast(`Capture stopped: ${cap.error}`, true, 8000);
    else toast(cap.failed ? `Pictures updated. ${plural(cap.failed, "plugin")} couldn't be captured` : "Pictures updated", cap.failed > 0);
  }
  S.wasCapturing = cap.running;
  if (S.selected && !pluginById(S.selected)) S.selected = null;
  render();
  refreshSheet();
}

async function poll() {
  try {
    await load();
  } catch (e) {
    console.error(e);  // one bad refresh must not stop Ordel refreshing for good
  } finally {
    setTimeout(poll, S.data?.capture.running ? 1000 : 3000);
  }
}

async function send(id) {
  const p = pluginById(id);
  if (!p) return;
  try {
    const variant = p.variants.length ? versionOf(p) : undefined;
    const r = await api("/api/send", { id, variant });
    const label = p.variants.length ? ` (${versionLabel(p)})` : "";
    if (r.ok) toast(`Added ${p.name}${label} to ${r.detail || "track"}`);
    else toast(SEND_ERRORS[r.detail] || `Couldn't add ${p.name}`, true);
  } catch (e) {
    toast(`Couldn't add ${p.name}`, true);
  }
  load();
}

async function updatePlugin(id, fields) {
  try {
    await api("/api/plugin", { id, ...fields });
  } catch (e) {
    toast(e.message, true);
  }
  await load();
}

async function saveSettings(fields) {
  const r = await api("/api/settings", fields);
  S.data.settings = r.settings;
  render();
  return r;
}

async function connect() {
  try {
    await api("/api/bridge/install", {});
  } catch (e) {
    return toast(`Couldn't set up REAPER: ${e.message}`, true, 8000);
  }
  toast("Connecting to REAPER…");
  setTimeout(load, 1500);
}

function select(id, focus = false) {
  S.selected = id;
  render();
  if (focus) document.querySelector(`.card[data-id="${id}"]`)?.focus();
}

function setView(view) {
  S.view = view;
  S.chip = null;
  S.gridSig = "";
  S.selected = null;  // Enter and F act on the selected plugin, which must not linger out of sight
  C.selected = null;
  C.saving = false;
  saveSettings({ last_view: view }).catch(() => {});
  $("#scroller").scrollTop = 0;
  render();
}

const actions = {
  connect,
  refresh: async () => {
    const before = new Set(S.data.plugins.map((p) => p.id));
    S.data = await api("/api/refresh", {});
    const after = new Set(S.data.plugins.map((p) => p.id));
    const added = [...after].filter((id) => !before.has(id)).length;
    const removed = [...before].filter((id) => !after.has(id)).length;
    toast(added || removed
      ? `Plugin list updated: ${added} added, ${removed} removed`
      : "No changes. Rescan plugins in REAPER's Preferences first, then refresh.");
    render();
    refreshSheet();
  },
  "search-all": () => setView("all"),
  "close-detail": () => select(null),
  "close-sheet": closeSheet,
  send: () => send(S.selected),
  favourite: () => { const p = pluginById(S.selected); updatePlugin(p.id, { favourite: !p.favourite }); },
  "reset-category": () => updatePlugin(S.selected, { category: null }),
  retake: async () => {  // the version shown in the details
    const p = pluginById(S.selected);
    await api("/api/capture", { action: "retake", id: p?.variants.length ? versionOf(p) : S.selected });
    load();
  },
  "custom-image": async () => { const r = await api("/api/custom-image", { id: S.selected }); if (r.ok) toast("Picture updated"); load(); },
  "capture-new": async () => { await api("/api/capture", { action: "capture_new" }); load(); },
  "dismiss-new": async () => { await api("/api/capture", { action: "dismiss_new" }); load(); },
  "capture-missing": async () => { await api("/api/capture", { action: "start" }); load(); },
  "recapture-all": async () => { await api("/api/capture", { action: "recapture_all" }); closeSheet(); load(); },
  "finish-welcome": async () => {
    await saveSettings({ onboarded: true });
    closeSheet();
    if (!S.data.settings.toured) startTour();
  },
  "replay-tour": () => { closeSheet(); startTour(); },
  "reset-appearance": () => saveSettings(APPEARANCE_DEFAULTS).then(refreshSheet),
  quit: () => api("/api/window", { action: "quit" }),
};

document.addEventListener("click", (e) => {
  // A shortcut another app (or Ordel) already owns never reaches the page: clicking away cancels recording.
  if (S.recording && !e.target.closest("#hotkey")) { S.recording = false; refreshSheet(); }
  const add = e.target.closest("[data-add]");
  if (add) return send(add.dataset.add);  // the + on a card
  const t = e.target.closest("[data-action],[data-version],[data-setting],[data-view],[data-mode],[data-chip],[data-capture],[data-window],[data-theme-opt],.card,#reaper-status,#open-settings,#hotkey");
  if (!t) return;
  if (t.dataset.action) return actions[t.dataset.action]?.();
  if (t.dataset.version) { S.versions[t.dataset.for || S.selected] = t.dataset.version; return render(); }
  if (t.dataset.view) return setView(t.dataset.view);
  if (t.dataset.mode) return saveSettings({ sidebar_mode: t.dataset.mode }).catch(() => {});
  if (t.dataset.chip !== undefined) { S.chip = t.dataset.chip || null; $("#scroller").scrollTop = 0; return render(); }
  if (t.dataset.capture) return api("/api/capture", { action: t.dataset.capture }).then(load);
  if (t.dataset.window) return api("/api/window", { action: t.dataset.window });
  if (t.dataset.themeOpt) return saveSettings({ theme: t.dataset.themeOpt }).then(refreshSheet);
  if (t.dataset.setting) return saveSettings({ [t.dataset.setting]: t.dataset.value }).then(refreshSheet);
  if (t.classList.contains("card")) {
    // Highlight now; open the details a moment later, so the panel sliding in can't move the cards
    // between the two clicks of a double-click (which would then miss, or hit another plugin).
    clearTimeout(S.openTimer);
    if (e.detail >= 2) return;  // second click of a double-click: the dblclick handler adds it
    const id = t.dataset.id;
    document.querySelectorAll(".card").forEach((el) => el.setAttribute("aria-selected", el.dataset.id === id));
    S.openTimer = setTimeout(() => select(id), 250);
    return;
  }
  if (t.id === "reaper-status" || t.id === "open-settings") return showSheet("settings");
  if (t.id === "hotkey") {
    S.recording = true;
    t.classList.add("recording");
    t.textContent = "Press a shortcut…";
  }
});

document.addEventListener("mousedown", (e) => {
  const edge = e.target.closest("[data-edge]")?.dataset.edge;
  if (edge && e.button === 0) {
    e.preventDefault();
    api("/api/window", { action: `resize-${edge}` }).catch(() => {});
  }
});

document.addEventListener("dblclick", (e) => {
  const card = e.target.closest(".card");
  if (card) { clearTimeout(S.openTimer); send(card.dataset.id); }
});

document.addEventListener("change", (e) => {
  if (e.target.id === "hide-after-add") saveSettings({ hide_after_add: e.target.checked });
  if (e.target.id === "show-developer") saveSettings({ show_developer: e.target.checked });
});

$("#search").addEventListener("input", (e) => { S.query = e.target.value; render(); });
$("#tile-size").addEventListener("input", (e) => document.documentElement.style.setProperty("--tile", `${e.target.value}px`));
$("#tile-size").addEventListener("change", (e) => saveSettings({ tile_size: Number(e.target.value) }));
$("#sheet-backdrop").addEventListener("mousedown", (e) => { if (e.target.id === "sheet-backdrop") closeSheet(); });

/* Drag a card onto a sidebar category to recategorise it. */
document.addEventListener("dragstart", (e) => {
  const card = e.target.closest(".card");
  if (card) e.dataTransfer.setData("text/plain", card.dataset.id);
});
document.addEventListener("dragover", (e) => {
  const item = e.target.closest('.nav-item[data-view^="cat:"]');
  document.querySelectorAll(".drop-target").forEach((el) => el !== item && el.classList.remove("drop-target"));
  if (item) { e.preventDefault(); item.classList.add("drop-target"); }
});
document.addEventListener("drop", (e) => {
  const item = e.target.closest('.nav-item[data-view^="cat:"]');
  document.querySelectorAll(".drop-target").forEach((el) => el.classList.remove("drop-target"));
  const id = e.dataTransfer.getData("text/plain");
  if (item && id) {
    e.preventDefault();
    const key = item.dataset.view.slice(4);
    updatePlugin(id, { category: key }).then(() => toast(`Moved ${pluginById(id)?.name} to ${catOf(key).label}`));
  }
});

/* ---------- keyboard ---------- */

function comboFromEvent(e) {
  const mods = [e.ctrlKey && "Ctrl", e.altKey && "Alt", e.shiftKey && "Shift", e.metaKey && "Win"].filter(Boolean);
  let key = null;
  // Letters by what the key types (AZERTY, QWERTZ...), other keys by position.
  if (/^[a-z]$/i.test(e.key)) key = e.key.toUpperCase();
  else if (/^Key[A-Z]$/.test(e.code)) key = e.code.slice(3);
  else if (/^Digit\d$/.test(e.code)) key = e.code.slice(5);
  else if (/^F\d{1,2}$/.test(e.code)) key = e.code;
  else if (e.code === "Space") key = "Space";
  return key && mods.length ? [...mods, key].join("+") : null;
}

function gridColumns() {
  return getComputedStyle($("#grid")).gridTemplateColumns.split(" ").length;
}

function moveSelection(delta) {
  const list = visiblePlugins();
  if (!list.length) return;
  const i = list.findIndex((p) => p.id === S.selected);
  const next = i < 0 ? 0 : Math.max(0, Math.min(list.length - 1, i + delta));
  select(list[next].id, true);
  document.querySelector(`.card[data-id="${list[next].id}"]`)?.scrollIntoView({ block: "nearest" });
}

document.addEventListener("keydown", async (e) => {
  if (S.recording) {
    e.preventDefault();
    if (e.key === "Escape") { S.recording = false; refreshSheet(); return; }
    const combo = comboFromEvent(e);
    if (!combo) return;
    S.recording = false;
    const r = await saveSettings({ hotkey: combo });
    $("#sheet").dataset.sig = "";
    refreshSheet();
    const err = $("#hotkey-error");
    if (!r.hotkey_ok && err) { err.hidden = false; err.textContent = `${combo} is already used by another app`; }
    return;
  }
  const inField = e.target.matches?.("input, select, textarea") ?? false;
  const sheetOpen = !$("#sheet-backdrop").hidden;

  if (e.key === "Escape") {
    if (document.activeElement?.classList.contains("help-btn")) return document.activeElement.blur();
    if (sheetOpen) return closeSheet();
    if (S.query) { S.query = ""; $("#search").value = ""; render(); return $("#search").blur(); }
    if (S.view === "chains" && C.selected) { C.selected = null; return render(); }
    if (S.selected) return select(null);
    return api("/api/window", { action: "hide" });
  }
  if (e.ctrlKey && e.key === ",") { e.preventDefault(); return showSheet("settings"); }
  if (sheetOpen) return;
  if (e.ctrlKey && e.key.toLowerCase() === "f") { e.preventDefault(); return $("#search").select(); }

  const arrows = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -gridColumns(), ArrowDown: gridColumns() };
  if (e.key in arrows && (!inField || (e.target.id === "search" && (e.key === "ArrowDown" || e.key === "ArrowUp")))) {
    e.preventDefault();
    return moveSelection(arrows[e.key]);
  }
  const sendTarget = e.target === document.body || e.target.id === "search" || e.target.classList.contains("card");
  if (e.key === "Enter" && S.selected && sendTarget) {
    e.preventDefault();
    return send(S.selected);
  }
  if (inField) return;
  if (e.key.toLowerCase() === "f" && !e.ctrlKey && !e.altKey && S.selected) return actions.favourite();
  if (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey && e.key !== " ") $("#search").focus();
});

/* ---------- start ---------- */

$("#search-icon").outerHTML = icon("search");
$("#open-settings").innerHTML = icon("sliders");
document.querySelector('[data-window="minimize"]').innerHTML = icon("minus");
document.querySelector('[data-window="hide"]').innerHTML = icon("close");

(async () => {
  await load();
  if (!S.data) return setTimeout(() => location.reload(), 1000);
  S.view = S.data.settings.last_view || "all";
  if (!S.data.plugins.some((p) => inView(p, S.view)) && /^(cat|dev):/.test(S.view)) S.view = "all";
  render();
  if (!S.data.settings.onboarded) showSheet("welcome");
  else if (!S.data.settings.toured) startTour();
  setTimeout(poll, 3000);
  window.addEventListener("focus", () => { if (tour.at < 0) $("#search").focus(); });  // not under the tour
})();

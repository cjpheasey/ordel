"use strict";

// The Chains page: saved groups of plugins that go onto REAPER in one click.

const C = { selected: null, showHidden: false, saving: false, adding: "", deleting: new Set() };

const chains = () => (S.data.chains || []).filter((c) => !C.deleting.has(c.id));
const chainById = (id) => chains().find((c) => c.id === id);
const visibleChains = () => {
  const words = S.query.toLowerCase().split(/\s+/).filter(Boolean);
  return chains().filter((c) => (C.showHidden || !c.hidden) &&
    words.every((w) => `${c.name} ${c.plugins.map((p) => p.name).join(" ")}`.toLowerCase().includes(w)));
};

function thumb(p) {
  const plugin = p.id && pluginById(p.id);
  return plugin && hasPicture(plugin)
    ? `<span class="thumb"><img src="${shotUrl(plugin)}" alt="" loading="lazy"></span>`
    : `<span class="thumb ph-thumb">${esc(initials(p.name))}</span>`;
}

function chainCardHtml(c) {
  const shown = c.plugins.slice(0, 6);
  const more = c.plugins.length - shown.length;
  return `<li class="chain-item${c.id === C.selected ? " selected" : ""}">
    <button class="chain-card" data-chain-apply="${esc(c.id)}" title="${c.return_track ? `Add ${esc(c.name)} as a return track` : `Put ${esc(c.name)} on the selected tracks`}">
      <span class="strip">${shown.map(thumb).join("")}${more > 0 ? `<span class="thumb more">+${more}</span>` : ""}${c.plugins.length ? "" : '<span class="thumb more">Empty</span>'}</span>
      <span class="chain-meta"><span class="name">${esc(c.name)}</span>
        <span class="sub">${plural(c.plugins.length, "plugin")}${c.return_track ? " · Return track" : ""}${c.hidden ? " · Hidden" : ""}</span></span>
    </button>
    <button class="icon-btn chain-edit" data-chain-edit="${esc(c.id)}" aria-label="Edit ${esc(c.name)}" title="Edit">${icon("sliders")}</button>
  </li>`;
}

function chainsEmpty() {
  if (S.query) return `<div class="glyph">${icon("search")}</div><h2>No chains match “${esc(S.query)}”</h2>`;
  return `<div class="glyph">${icon("chain")}</div><h2>No chains yet</h2>
    <p>Set up plugins on a track in REAPER, select the track, then press Save from selected track. Your REAPER chains show up here too.</p>`;
}

function renderChainTools() {
  const bar = $("#chain-tools");
  bar.hidden = S.view !== "chains";
  if (bar.hidden) return;
  const hidden = chains().filter((c) => c.hidden).length;
  const sig = `${C.saving}|${hidden}|${C.showHidden}|${S.data.reaper.connected}`;
  if (bar.dataset.sig === sig) return;
  bar.dataset.sig = sig;
  setHtml(bar, C.saving
    ? `<form class="save-chain" data-chain-form="save"><input id="chain-name" placeholder="Name this chain" maxlength="80" autocomplete="off" aria-label="Chain name">
        <button class="btn primary" type="submit">Save</button><button class="btn quiet" type="button" data-chain-act="cancel-save">Cancel</button></form>`
    : `<button class="btn" data-chain-act="start-save" ${S.data.reaper.connected ? "" : "disabled"}>${icon("plus")}Save from selected track</button>
       <button class="btn quiet" data-chain-act="build">Build a chain</button>
       ${hidden ? `<button class="btn quiet" data-chain-act="toggle-hidden">${C.showHidden ? "Hide hidden" : `Show hidden (${hidden})`}</button>` : ""}`);
  if (C.saving) $("#chain-name").focus();
}

function renderChains() {
  const list = visibleChains();
  const sig = "chains|" + S.query + "|" + C.selected + "|" + JSON.stringify(list) + list.map((c) => c.plugins.map((p) => pluginById(p.id)?.shot || 0).join()).join();
  if (sig !== S.gridSig) {
    $("#grid").innerHTML = list.map(chainCardHtml).join("");
    S.gridSig = sig;
  }
  $("#grid").classList.add("chain-grid");
  $("#empty").hidden = list.length > 0;
  if (!list.length) $("#empty").innerHTML = chainsEmpty();
}

function versionName(p) {
  const plugin = p.id && pluginById(p.id);
  const label = plugin?.variants.find((v) => v.id === p.variant)?.label;
  return label && label !== "Stereo" ? `${p.name} (${label})` : p.name;
}

function renderChainDetail() {
  const panel = $("#detail");
  const c = C.selected && chainById(C.selected);
  if (!c) { panel.hidden = true; panel.dataset.id = ""; return; }
  const sig = JSON.stringify(c) + C.adding + S.data.reaper.connected;
  if (!panel.hidden && panel.dataset.sig === sig) return;
  const typing = document.activeElement?.id === "chain-add-search";
  panel.hidden = false;
  panel.dataset.id = c.id;
  panel.dataset.sig = sig;
  const built = c.kind === "built";
  const rows = c.plugins.map((p, i) => `<li class="chain-row">${thumb(p)}<span class="nm">${esc(versionName(p))}${p.id ? "" : ' <span class="missing">Not installed</span>'}</span>
      ${built ? `<span class="row-tools">
        <button class="icon-btn" data-chain-act="plugin-up" data-index="${i}" aria-label="Move up" ${i ? "" : "disabled"}>${icon("chevron", "up")}</button>
        <button class="icon-btn" data-chain-act="plugin-down" data-index="${i}" aria-label="Move down" ${i < c.plugins.length - 1 ? "" : "disabled"}>${icon("chevron", "down")}</button>
        <button class="icon-btn" data-chain-act="plugin-remove" data-index="${i}" aria-label="Remove">${icon("close")}</button></span>` : ""}</li>`).join("");
  const words = C.adding.toLowerCase().split(/\s+/).filter(Boolean);
  const matches = words.length ? S.data.plugins.flatMap((p) => (p.variants.length ? p.variants : [{ id: p.id, label: "" }])
    .map((v) => ({ p, v }))).filter(({ p, v }) => words.every((w) => `${p.name} ${devOf(p)} ${v.label}`.toLowerCase().includes(w))).slice(0, 6) : [];
  panel.innerHTML = `
    <div class="detail-head"><button class="icon-btn" data-chain-act="close" aria-label="Close details">${icon("close")}</button></div>
    <div class="detail-body chain-detail">
      ${c.ordel ? `<input class="chain-title" id="chain-rename" value="${esc(c.name)}" maxlength="80" aria-label="Chain name">`
                : `<div><h2>${esc(c.name)}</h2><div class="vendor-line">Saved in REAPER</div></div>`}
      <div class="actions">
        <button class="btn primary" data-chain-apply="${esc(c.id)}" ${S.data.reaper.connected ? "" : "disabled"}>${icon("plus")}${c.return_track ? "Add as return track" : "Add to selected tracks"}</button>
      </div>
      <div class="fields">
        <div class="field"><label class="k" for="chain-return">Use as return track<small>Adds a new track with this chain, for sends</small></label>
          <input type="checkbox" class="switch" id="chain-return" ${c.return_track ? "checked" : ""}></div>
      </div>
      <ol class="chain-rows">${rows || '<li class="chain-row empty-row">No plugins yet</li>'}</ol>
      ${built ? `<div class="chain-add"><input id="chain-add-search" type="search" placeholder="Add a plugin…" value="${esc(C.adding)}" autocomplete="off" aria-label="Find a plugin to add">
        ${matches.length ? `<ul class="chain-matches">${matches.map(({ p, v }) => `<li><button data-chain-act="plugin-add" data-add-version="${v.id}" class="match">${esc(p.name)}${v.label && v.label !== "Stereo" ? ` <span class="sub">${esc(v.label)}</span>` : ""}</button></li>`).join("")}</ul>` : ""}</div>` : ""}
      <div class="picture-actions">
        ${c.ordel ? `<button class="btn quiet" data-chain-act="resave" ${S.data.reaper.connected ? "" : "disabled"}>${icon("refresh")}${built ? "Save with settings from selected track" : "Replace with selected track"}</button>` : ""}
        <button class="btn quiet" data-chain-act="move-up">${icon("chevron", "up")}Move up in the list</button>
        <button class="btn quiet" data-chain-act="move-down">${icon("chevron", "down")}Move down in the list</button>
        ${c.ordel ? `<button class="btn quiet danger" data-chain-act="delete">${icon("close")}Delete chain</button>`
                  : `<button class="btn quiet" data-chain-act="hide">${icon("minus")}${c.hidden ? "Show in Ordel" : "Hide from Ordel"}</button>`}
      </div>
    </div>`;
  if (typing) { const s = $("#chain-add-search"); s.focus(); s.setSelectionRange(s.value.length, s.value.length); }
}

async function chainCall(action, fields = {}) {
  try {
    return await api("/api/chain", { action, ...fields });
  } catch (e) {
    toast(e.message, true);
    return null;
  } finally {
    await load();
  }
}

async function applyChain(id) {
  const c = chainById(id);
  if (!c) return;
  const r = await chainCall("apply", { id });
  if (!r) return;
  if (!r.ok) return toast(r.detail === "NO_TRACK" ? "Select a track in REAPER first" : (SEND_ERRORS[r.detail] || `Couldn't add ${c.name}`), true);
  let text = r.exists ? `A ${c.name} return already exists in this project. Added another.`
    : c.return_track ? `Added a ${c.name} return track` : `Added ${c.name} to ${plural(r.tracks, "track")}`;
  if (r.missing.length) text += `${text.endsWith(".") ? "" : "."} Not installed: ${r.missing.join(", ")}.`;
  toast(text, r.exists || r.missing.length > 0, r.missing.length || r.exists ? 6000 : 2600);
}

async function saveChain(name, replace) {
  const r = await chainCall("save", replace ? { name, replace } : { name });
  if (!r) return;
  if (!r.ok) return toast({ NO_TRACK: "Select a track in REAPER first", NO_FX: "The selected track has no plugins to save" }[r.detail] || SEND_ERRORS[r.detail] || "Couldn't save the chain", true);
  C.selected = r.id;
  toast(`Saved ${name}`);
}

function editPlugins(c, change) {
  const ids = c.plugins.map((p) => p.variant).filter(Boolean);
  change(ids);
  return chainCall("update", { id: c.id, plugins: ids });
}

function deleteChain(c) {
  C.deleting.add(c.id);
  C.selected = null;
  render();
  let undone = false;
  toast(`Deleted ${c.name}`, false, 6000, { label: "Undo", run: () => { undone = true; C.deleting.delete(c.id); render(); } });
  setTimeout(async () => {
    if (undone) return;
    await chainCall("delete", { id: c.id });
    C.deleting.delete(c.id);
  }, 6000);
}

const chainActions = {
  "start-save": () => { C.saving = true; render(); },
  "cancel-save": () => { C.saving = false; render(); },
  "toggle-hidden": () => { C.showHidden = !C.showHidden; render(); },
  build: async () => {
    const r = await chainCall("build", { name: "New chain", plugins: [] });
    if (r) { C.selected = r.id; render(); $("#chain-rename")?.select(); }
  },
  close: () => { C.selected = null; render(); },
  resave: (c) => saveChain(c.name, c.id),
  "move-up": (c) => chainCall("move", { id: c.id, delta: -1 }),
  "move-down": (c) => chainCall("move", { id: c.id, delta: 1 }),
  hide: (c) => chainCall("hide", { id: c.id, hidden: !c.hidden }),
  delete: deleteChain,
  "plugin-up": (c, el) => editPlugins(c, (ids) => { const i = +el.dataset.index; [ids[i - 1], ids[i]] = [ids[i], ids[i - 1]]; }),
  "plugin-down": (c, el) => editPlugins(c, (ids) => { const i = +el.dataset.index; [ids[i + 1], ids[i]] = [ids[i], ids[i + 1]]; }),
  "plugin-remove": (c, el) => editPlugins(c, (ids) => ids.splice(+el.dataset.index, 1)),
  "plugin-add": (c, el) => { C.adding = ""; return editPlugins(c, (ids) => ids.push(el.dataset.addVersion)); },
};

document.addEventListener("click", (e) => {
  const apply = e.target.closest("[data-chain-apply]");
  if (apply) return applyChain(apply.dataset.chainApply);
  const edit = e.target.closest("[data-chain-edit]");
  if (edit) { C.selected = C.selected === edit.dataset.chainEdit ? null : edit.dataset.chainEdit; return render(); }
  const act = e.target.closest("[data-chain-act]");
  if (act) chainActions[act.dataset.chainAct]?.(chainById(C.selected), act);
});

document.addEventListener("submit", (e) => {
  if (e.target.dataset.chainForm !== "save") return;
  e.preventDefault();
  const name = $("#chain-name").value.trim();
  if (!name) return $("#chain-name").focus();
  C.saving = false;
  saveChain(name);
});

document.addEventListener("input", (e) => {
  if (e.target.id === "chain-add-search") { C.adding = e.target.value; renderChainDetail(); }
});

document.addEventListener("change", (e) => {
  const c = chainById(C.selected);
  if (!c) return;
  if (e.target.id === "chain-return") chainCall("update", { id: c.id, return_track: e.target.checked });
  if (e.target.id === "chain-rename" && e.target.value.trim() && e.target.value.trim() !== c.name) {
    chainCall("update", { id: c.id, name: e.target.value.trim() }).then((r) => { if (r?.id) { C.selected = r.id; render(); } });
  }
});

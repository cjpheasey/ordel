"use strict";

// Categories you make yourself: create one from the sidebar, change it from its title.

const CUSTOM_COLOURS = ["#F2A7C3", "#7FD1AE", "#F5B971", "#9DB4FF", "#C9A15A", "#E07A5F", "#81B29A", "#B8A1E3"];
const K = { adding: false, deleting: new Set() };

function newCategoryRow() {
  return K.adding
    ? `<form class="new-cat" data-cat-form="new"><input id="new-cat-name" maxlength="40" placeholder="Name, then Enter" aria-label="New category name" autocomplete="off"></form>`
    : `<button class="nav-item new-cat-btn" data-cat-act="start">${icon("plus")}<span class="label">New category</span></button>`;
}

function editCategoryButton() {
  const c = S.view.startsWith("cat:") && catOf(S.view.slice(4));
  return c && c.custom
    ? `<button class="icon-btn cat-edit" data-cat-act="edit" aria-label="Edit ${esc(c.label)}" title="Rename, recolour or delete">${icon("sliders")}</button>`
    : "";
}

function categorySheetHtml(c) {
  return `
    <div class="sheet-head"><h2 id="sheet-title">Edit category</h2><button class="icon-btn" data-action="close-sheet" aria-label="Close">${icon("close")}</button></div>
    <div class="sheet-body cat-sheet">
      <label class="k" for="cat-name">Name</label>
      <input id="cat-name" class="cat-name" value="${esc(c.label)}" maxlength="40" autocomplete="off" data-autofocus>
      <span class="k">Colour</span>
      <span class="cat-swatches">${CUSTOM_COLOURS.map((col) =>
        `<button class="accent-opt" data-cat-colour="${col}" aria-pressed="${col.toLowerCase() === c.color.toLowerCase()}" aria-label="Colour ${col}" style="background:${col}"></button>`).join("")}</span>
    </div>
    <div class="sheet-foot"><button class="btn quiet danger" data-cat-act="delete">${icon("close")}Delete category</button><button class="btn primary" data-action="close-sheet">Done</button></div>`;
}

// ---------- the category picker in a plugin's details (a native list can't show colours) ----------

function closeCategoryMenu(focusButton = false) {
  const menu = $("#cat-menu");
  if (!menu) return;
  menu.remove();
  const button = $("#category-button");
  button?.setAttribute("aria-expanded", "false");
  if (focusButton) button?.focus();
}

function openCategoryMenu(button) {
  const p = pluginById(S.selected);
  if (!p) return;
  closeCategoryMenu();
  const item = (c) => `<li role="option" tabindex="-1" data-pick-cat="${c.key}" aria-selected="${c.key === p.category}">
      <span class="tag${c.key === "uncategorised" ? " uncat" : ""}" style="--c:${c.color}"></span><span class="nm">${esc(c.label)}</span>${c.key === p.category ? icon("check") : ""}</li>`;
  const builtIn = cats().filter((c) => !c.custom && c.key !== "uncategorised");
  const mine = cats().filter((c) => c.custom);
  const uncat = cats().find((c) => c.key === "uncategorised");
  const menu = document.createElement("ul");
  menu.id = "cat-menu";
  menu.className = "cat-menu";
  menu.setAttribute("role", "listbox");
  menu.setAttribute("aria-label", "Category");
  menu.innerHTML = builtIn.map(item).join("")
    + (mine.length ? `<li class="cat-menu-head" role="presentation">Yours</li>${mine.map(item).join("")}` : "")
    + `<li class="cat-menu-sep" role="presentation"></li>${uncat ? item(uncat) : ""}`;
  document.body.append(menu);
  // Like a Mac pop-up menu: the whole list opens over the button, with the current category sitting
  // exactly where the button was, then nudged to stay on screen (it scrolls only in a very short window).
  const r = button.getBoundingClientRect();
  const width = Math.max(r.width + 24, 240);
  menu.style.width = `${width}px`;
  menu.style.left = `${Math.max(12, Math.min(r.right + 12 - width, innerWidth - width - 12))}px`;
  menu.style.maxHeight = `${innerHeight - 24}px`;
  const height = menu.offsetHeight;
  const current = menu.querySelector('[aria-selected="true"]') || menu.querySelector("[data-pick-cat]");
  const lined = r.top + r.height / 2 - (current.offsetTop + current.offsetHeight / 2);
  menu.style.top = `${Math.max(12, Math.min(lined, innerHeight - height - 12))}px`;
  button.setAttribute("aria-expanded", "true");
  current.focus();
  current.scrollIntoView({ block: "nearest" });
}

document.addEventListener("click", (e) => {
  const pick = e.target.closest("[data-pick-cat]");
  if (pick) {
    const key = pick.dataset.pickCat;
    closeCategoryMenu(true);
    if (key !== pluginById(S.selected)?.category) updatePlugin(S.selected, { category: key });
    return;
  }
  const button = e.target.closest("#category-button");
  if (button) return $("#cat-menu") ? closeCategoryMenu() : openCategoryMenu(button);
  if (!e.target.closest("#cat-menu")) closeCategoryMenu();
});

document.addEventListener("keydown", (e) => {
  const menu = $("#cat-menu");
  if (!menu) return;
  const items = [...menu.querySelectorAll("[data-pick-cat]")];
  const i = items.indexOf(document.activeElement);
  const go = (n) => { e.preventDefault(); items[(n + items.length) % items.length].focus(); };
  if (e.key === "ArrowDown") go(i + 1);
  else if (e.key === "ArrowUp") go(i - 1);
  else if (e.key === "Home") go(0);
  else if (e.key === "End") go(items.length - 1);
  else if ((e.key === "Enter" || e.key === " ") && i >= 0) { e.preventDefault(); items[i].click(); }
  else if (e.key === "Escape" || e.key === "Tab") { e.preventDefault(); closeCategoryMenu(true); }
  else return;
  e.stopPropagation();  // the app's own keys (Esc closes the details, letters search) stay out of the menu
}, true);

window.addEventListener("resize", () => closeCategoryMenu());
document.addEventListener("scroll", (e) => { if (!e.target.closest?.("#cat-menu")) closeCategoryMenu(); }, true);

async function catCall(action, fields) {
  try {
    return await api("/api/category", { action, ...fields });
  } catch (e) {
    toast(e.message, true);
    return null;
  } finally {
    await load();
  }
}

function currentCategory() {
  return S.view.startsWith("cat:") ? catOf(S.view.slice(4)) : null;
}

function showCategorySheet(c) {
  $("#sheet").dataset.kind = "category";
  openSheet(categorySheetHtml(c));
  $("#cat-name").select();
}

function deleteCategory(c) {
  K.deleting.add(c.key);
  closeSheet();
  setView("all");
  let undone = false;
  toast(`Deleted ${c.label}. Its plugins go back to their detected categories.`, false, 6000, {
    label: "Undo", run: () => { undone = true; K.deleting.delete(c.key); render(); },
  });
  setTimeout(async () => {
    if (undone) return;
    await catCall("delete", { key: c.key });
    K.deleting.delete(c.key);
  }, 6000);
}

document.addEventListener("click", (e) => {
  const colour = e.target.closest("[data-cat-colour]");
  if (colour) {
    const c = currentCategory();
    if (c) catCall("update", { key: c.key, color: colour.dataset.catColour }).then(() => showCategorySheet(currentCategory()));
    return;
  }
  const act = e.target.closest("[data-cat-act]")?.dataset.catAct;
  if (act === "start") { K.adding = true; render(); $("#new-cat-name")?.focus(); }
  if (act === "edit" && currentCategory()) showCategorySheet(currentCategory());
  if (act === "delete" && currentCategory()) deleteCategory(currentCategory());
});

document.addEventListener("submit", async (e) => {
  if (e.target.dataset.catForm !== "new") return;
  e.preventDefault();
  const label = $("#new-cat-name").value.trim();
  if (!label) return;
  const made = await catCall("add", { label });
  if (!made) return $("#new-cat-name")?.focus();
  K.adding = false;
  setView(`cat:${made.key}`);
  toast(`Made ${made.label}. Drag plugins onto it in the sidebar, or pick it in a plugin's details.`, false, 5000);
});

document.addEventListener("keydown", (e) => {
  if (e.target.id === "new-cat-name" && e.key === "Escape") { e.stopPropagation(); K.adding = false; render(); }
}, true);

document.addEventListener("focusout", (e) => {
  if (e.target.id === "new-cat-name" && !e.target.value.trim()) setTimeout(() => { K.adding = false; render(); }, 150);
});

document.addEventListener("change", (e) => {
  const c = currentCategory();
  if (e.target.id === "cat-name" && c && e.target.value.trim() && e.target.value.trim() !== c.label) {
    catCall("update", { key: c.key, label: e.target.value.trim() });
  }
});

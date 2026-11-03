"use strict";

// A short first-run tour: each step spotlights one part of the real interface with a card beside it.
const TOUR_STEPS = [
  {
    target: ".brand",
    title: "One shortcut away",
    body: () => `Press <kbd>${esc(S.data.settings.hotkey)}</kbd> in any app, even REAPER, to show or hide Ordel.`,
  },
  {
    target: "#nav-switch",
    title: "Browse your way",
    body: () => "Switch between categories and developers. To move a plugin to another category, drag its card onto one.",
  },
  {
    target: ".search",
    title: "Find it fast",
    body: () => "Start typing anywhere to search by name, developer or category.",
  },
  {
    target: ".card",
    title: "Add it to your track",
    body: () => "Double-click a plugin, or press Enter, to put it on the selected REAPER track. Click once to see its details.",
  },
  {
    target: "#open-settings",
    title: "Make it yours",
    body: () => "Themes, your shortcut and the REAPER connection live in Settings. You can replay this tour there too.",
  },
];

const tour = { steps: [], at: -1, els: null };

function startTour() {
  tour.steps = TOUR_STEPS.filter((s) => document.querySelector(s.target));
  if (!tour.steps.length) return;
  if (!tour.els) {
    const blocker = document.createElement("div");
    blocker.className = "tour-blocker";
    const spot = document.createElement("div");
    spot.className = "tour-spot";
    const card = document.createElement("div");
    card.className = "tour-card";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-modal", "true");
    card.setAttribute("aria-labelledby", "tour-title");
    document.body.append(blocker, spot, card);
    tour.els = { blocker, spot, card };
  }
  tour.at = 0;
  showTourStep();
}

function endTour() {
  if (tour.at < 0) return;
  tour.at = -1;
  Object.values(tour.els).forEach((el) => el.remove());
  tour.els = null;
  saveSettings({ toured: true }).catch(() => {});
  $("#search").focus();
}

function showTourStep() {
  const step = tour.steps[tour.at];
  const target = document.querySelector(step.target);
  if (!target) return endTour();
  target.scrollIntoView({ block: "nearest" });
  const last = tour.at === tour.steps.length - 1;
  const { spot, card } = tour.els;
  card.innerHTML = `
    <div class="tour-step">${tour.at + 1} of ${tour.steps.length}</div>
    <h2 id="tour-title">${esc(step.title)}</h2>
    <p>${step.body()}</p>
    <div class="tour-actions">
      <button class="btn quiet" data-tour="skip">${last ? "Close" : "Skip tour"}</button>
      <span class="tour-nav">
        ${tour.at > 0 ? '<button class="btn" data-tour="back">Back</button>' : ""}
        <button class="btn primary" data-tour="next">${last ? "Done" : "Next"}</button>
      </span>
    </div>`;
  placeTour(target, spot, card);
  card.querySelector('[data-tour="next"]').focus();
}

function placeTour(target, spot, card) {
  const pad = 6, gap = 14, edge = 16;
  const r = target.getBoundingClientRect();
  Object.assign(spot.style, {
    left: `${r.left - pad}px`, top: `${r.top - pad}px`,
    width: `${r.width + pad * 2}px`, height: `${r.height + pad * 2}px`,
  });
  const w = card.offsetWidth, h = card.offsetHeight;
  const vw = window.innerWidth, vh = window.innerHeight;
  // Prefer the right of the target, then below, then left, then above.
  const options = [
    { left: r.right + pad + gap, top: r.top, fits: r.right + pad + gap + w <= vw - edge },
    { left: r.left, top: r.bottom + pad + gap, fits: r.bottom + pad + gap + h <= vh - edge },
    { left: r.left - pad - gap - w, top: r.top, fits: r.left - pad - gap - w >= edge },
    { left: r.left, top: r.top - pad - gap - h, fits: r.top - pad - gap - h >= edge },
  ];
  const pick = options.find((o) => o.fits) || options[1];
  card.style.left = `${Math.min(Math.max(pick.left, edge), vw - w - edge)}px`;
  card.style.top = `${Math.min(Math.max(pick.top, edge), vh - h - edge)}px`;
}

function moveTour(delta) {
  const next = tour.at + delta;
  if (next >= tour.steps.length) return endTour();
  if (next < 0) return;
  tour.at = next;
  showTourStep();
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-tour]");
  if (!b) return;
  e.stopPropagation();
  if (b.dataset.tour === "next") moveTour(1);
  else if (b.dataset.tour === "back") moveTour(-1);
  else endTour();
}, true);

// Runs before the app's own keys, so Esc closes the tour instead of hiding the window.
document.addEventListener("keydown", (e) => {
  if (tour.at < 0) return;
  const keys = { Escape: () => endTour(), ArrowRight: () => moveTour(1), ArrowLeft: () => moveTour(-1) };
  if (keys[e.key]) {
    e.preventDefault();
    e.stopImmediatePropagation();
    keys[e.key]();
  } else if (e.key === "Tab") {  // keep focus inside the card
    e.preventDefault();
    e.stopImmediatePropagation();
    const buttons = [...tour.els.card.querySelectorAll("button")];
    const i = buttons.indexOf(document.activeElement);
    buttons[(i + (e.shiftKey ? -1 : 1) + buttons.length) % buttons.length].focus();
  } else if (e.key !== "Enter" && e.key !== " ") {
    e.stopImmediatePropagation();  // typing doesn't reach the search box mid-tour
  }
}, true);

window.addEventListener("resize", () => {
  if (tour.at >= 0) placeTour(document.querySelector(tour.steps[tour.at].target), tour.els.spot, tour.els.card);
});

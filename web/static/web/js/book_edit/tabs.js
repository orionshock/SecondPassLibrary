export function initTabs() {
  const buttons = Array.from(document.querySelectorAll(".tab-button[data-tab]"));
  const panels = Array.from(document.querySelectorAll("[data-tab-panel]"));
  if (!buttons.length || !panels.length) return;

  function show(tab) {
    for (const btn of buttons) btn.classList.toggle("is-active", btn.dataset.tab === tab);
    for (const panel of panels) panel.classList.toggle("is-hidden", panel.dataset.tabPanel !== tab);
  }

  for (const btn of buttons) btn.addEventListener("click", () => show(btn.dataset.tab || "metadata"));
  show("metadata");
}


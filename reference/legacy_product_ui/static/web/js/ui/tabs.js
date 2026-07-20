export function initTabs(root, options = {}) {
  const scope = root || document;
  const groups = Array.from(scope.querySelectorAll(".tabs"));
  if (!groups.length) {
    initTabGroup(scope, scope, options);
    return;
  }
  for (const group of groups) {
    const panelRoot =
      group.closest("[data-tab-root]") || group.closest("section") || group.parentElement || scope;
    initTabGroup(group, panelRoot, options);
  }
}

function initTabGroup(buttonRoot, panelRoot, options) {
  if (!buttonRoot || !panelRoot) return;
  const buttons = Array.from(buttonRoot.querySelectorAll(".tab-button[data-tab]"));
  const panelKeys = new Set(buttons.map((button) => button.getAttribute("data-tab")).filter(Boolean));
  const panels = Array.from(panelRoot.querySelectorAll("[data-tab-panel]")).filter((panel) =>
    panelKeys.has(panel.getAttribute("data-tab-panel"))
  );
  if (!buttons.length || !panels.length) return;

  function activate(tab) {
    if (!tab) return;
    const matchedPanel = panels.some((panel) => panel.getAttribute("data-tab-panel") === tab);
    if (!matchedPanel) return;
    for (const panel of panels) {
      const isActive = panel.getAttribute("data-tab-panel") === tab;
      panel.classList.toggle("is-hidden", !isActive);
      if (panel.getAttribute("role") === "tabpanel") {
        panel.setAttribute("aria-hidden", isActive ? "false" : "true");
      }
    }

    for (const button of buttons) {
      const isActive = button.getAttribute("data-tab") === tab;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-selected", isActive ? "true" : "false");
    }
  }

  for (const button of buttons) {
    button.addEventListener("click", () => activate(button.getAttribute("data-tab") || ""));
  }

  const activeButton = buttons.find((button) => button.classList.contains("is-active"));
  const initialTab =
    (activeButton && activeButton.getAttribute("data-tab")) ||
    options.defaultTab ||
    buttons[0].getAttribute("data-tab") ||
    "";
  activate(initialTab);
}

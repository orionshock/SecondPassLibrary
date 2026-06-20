export function groupDisplayName(group) {
  if (!group || !group.name) return "Unknown group";
  const name = String(group.name).trim();
  return name || "Unknown group";
}

export function groupBadgeText(group) {
  return groupDisplayName(group);
}

export function renderGroupBadge(group, options = {}) {
  const badge = document.createElement(options.element || "span");
  badge.className = "group-badge";
  if (options.compact === true) badge.classList.add("group-badge--compact");
  if (options.className) badge.classList.add(String(options.className));

  const icon = document.createElement("span");
  icon.className = "material-symbols-outlined group-badge__icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "groups";
  badge.appendChild(icon);

  const name = document.createElement("span");
  name.className = "group-badge__name";
  name.textContent = groupDisplayName(group);
  badge.appendChild(name);

  return badge;
}

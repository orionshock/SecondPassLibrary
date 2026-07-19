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
  const isPublicGroup = !!(group && group.is_public_group);
  if (isPublicGroup) badge.classList.add("group-badge--public");
  if (options.compact === true) badge.classList.add("group-badge--compact");
  if (options.className) badge.classList.add(String(options.className));

  const icon = document.createElement("span");
  icon.className = "material-symbols-outlined group-badge__icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = isPublicGroup ? "public" : "groups";
  badge.appendChild(icon);

  const name = document.createElement("span");
  name.className = "group-badge__name";
  name.textContent = groupDisplayName(group);
  badge.appendChild(name);

  return badge;
}

export function renderPublicCuratorRestriction() {
  const note = document.createElement("div");
  note.className = "membership-row__note muted public-curator-note";

  const label = document.createElement("span");
  label.textContent = "Public Group";
  note.appendChild(label);

  const helpText = "Only Librarians/Managers may Curate the Public Group";
  const help = document.createElement("span");
  help.className = "public-curator-note__help";
  help.tabIndex = 0;
  help.setAttribute("aria-label", helpText);
  help.setAttribute("title", helpText);

  const icon = document.createElement("span");
  icon.className = "material-symbols-outlined public-curator-note__icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "help";
  help.appendChild(icon);
  note.appendChild(help);

  return note;
}

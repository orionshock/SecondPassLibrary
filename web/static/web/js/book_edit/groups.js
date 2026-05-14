import { clear, el } from "./shared.js";

export function renderGroups({ groups, groupsEl }) {
  clear(groupsEl);
  if (!groups.length) {
    groupsEl.appendChild(el("div", "muted", "No visible groups."));
    return;
  }
  const ul = document.createElement("ul");
  const items = groups.slice().sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")));
  for (const g of items) {
    const li = document.createElement("li");
    const gid = g && g.id != null ? String(g.id) : "";
    const a = el("a", "", g && g.name ? g.name : "");
    a.setAttribute("href", gid ? `/groups/${encodeURIComponent(gid)}/` : "#");
    li.appendChild(a);
    if (g && g.is_public_group) {
      li.appendChild(document.createTextNode(" "));
      li.appendChild(el("span", "pill pill--owner", "Public"));
    }
    if (gid) {
      li.appendChild(document.createTextNode(" "));
      const btn = el("button", "linklike", "Remove");
      btn.type = "button";
      btn.setAttribute("data-group-remove-id", gid);
      li.appendChild(btn);
    }
    ul.appendChild(li);
  }
  groupsEl.appendChild(ul);
}

export function syncGroupsAddOptions({ allGroups, groups, groupsAddSelectEl, groupsAddBtnEl }) {
  clear(groupsAddSelectEl);
  const currentIds = new Set(groups.map((g) => String(g.id)));
  const items = allGroups
    .slice()
    .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")))
    .filter((g) => g && g.id && !currentIds.has(String(g.id)))
    .slice(0, 500);
  if (!items.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "(No available groups)";
    groupsAddSelectEl.appendChild(opt);
    groupsAddBtnEl.disabled = true;
    return;
  }
  for (const g of items) {
    const opt = document.createElement("option");
    opt.value = String(g.id);
    opt.textContent = String(g.name || g.id);
    groupsAddSelectEl.appendChild(opt);
  }
  groupsAddBtnEl.disabled = false;
}


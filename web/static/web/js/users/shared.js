export function formatDateTime(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  try {
    return d.toLocaleString();
  } catch (_e) {
    return d.toISOString();
  }
}

export function curatedGroupsFromUser(user) {
  const groups = Array.isArray(user && user.groups) ? user.groups : [];
  const curated = groups.filter((g) => (g && g.membership_role) === "curator");
  return curated.map((g) => g.name || String(g.id || "")).filter(Boolean);
}

export function groupsSummary(user) {
  const groups = Array.isArray(user && user.groups) ? user.groups : [];
  if (!groups.length) return "";
  return groups
    .map((g) => {
      const name = g.name || String(g.id || "");
      if (!name) return "";
      const badge = g.membership_role ? ` (${g.membership_role})` : "";
      return `${name}${badge}`;
    })
    .filter(Boolean)
    .join(", ");
}

export function passesFilter(user, filter) {
  if (!user) return false;
  if (filter === "inactive") return user.is_active === false;
  if (filter === "readers") return (user.role || "") === "reader";
  if (filter === "librarians") return (user.role || "") === "librarian";
  if (filter === "curators") return curatedGroupsFromUser(user).length > 0;
  if (filter === "managers") return user.is_owner === true || (user.role || "") === "manager";
  return true;
}


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

export function passesFilter(user, filter) {
  if (!user) return false;
  if (filter === "inactive") return user.is_active === false;
  if (filter === "reader") return (user.role || "") === "reader";
  if (filter === "librarian") return (user.role || "") === "librarian";
  if (filter === "curator") {
    const groups = Array.isArray(user.groups) ? user.groups : [];
    return groups.some(
      (group) => group && group.is_curator === true
    );
  }
  if (filter === "manager") return user.is_owner === true || (user.role || "") === "manager";
  return true;
}

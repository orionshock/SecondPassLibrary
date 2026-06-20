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
  if (filter === "readers") return (user.role || "") === "reader";
  if (filter === "librarians") return (user.role || "") === "librarian";
  if (filter === "curators") {
    const groups = Array.isArray(user.groups) ? user.groups : [];
    return groups.some(
      (group) => group && group.membership_role === "curator"
    );
  }
  if (filter === "managers") return user.is_owner === true || (user.role || "") === "manager";
  return true;
}

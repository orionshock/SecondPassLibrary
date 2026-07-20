import { setBreadcrumbs } from "../ui/breadcrumbs.js";
import { userDisplayName } from "../ui/identity.js";

const USER_ROLE_FILTERS = new Set(["reader", "curator", "librarian", "manager"]);

export function usersFilterFromSearch(search = window.location.search) {
  const params = new URLSearchParams(search || "");
  const role = (params.get("role") || "").trim().toLowerCase();
  const status = (params.get("status") || "").trim().toLowerCase();
  if (role && status) return "all";
  if (status) return status === "inactive" ? "inactive" : "all";
  if (role) return USER_ROLE_FILTERS.has(role) ? role : "all";
  return "all";
}

export function usersFilterHref(filter = "all") {
  const search = new URLSearchParams();
  if (USER_ROLE_FILTERS.has(filter)) search.set("role", filter);
  if (filter === "inactive") search.set("status", "inactive");
  const query = search.toString();
  return query ? `/users/?${query}` : "/users/";
}

export function setUsersFilterUrl(filter, { replace = false } = {}) {
  const href = usersFilterHref(filter);
  if (replace) window.history.replaceState({}, "", href);
  else window.history.pushState({}, "", href);
}

export function userBreadcrumbLabel(user) {
  if (!user) return "User";
  const displayName = userDisplayName(user);
  if (displayName) return displayName;
  if (user.username) return String(user.username).trim() || "User";
  if (user.email) return String(user.email).trim() || "User";
  return "User";
}

export function syncUserEditBreadcrumb(user) {
  setBreadcrumbs([
    { label: "Users", href: "/users/" },
    { label: userBreadcrumbLabel(user) },
    { label: "Edit", current: true },
  ]);
}

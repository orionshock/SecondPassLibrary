export function roleOf(me) {
  return me && me.role ? String(me.role) : "";
}

export function isOwner(me) {
  return !!(me && me.is_owner === true);
}

export function isManager(me) {
  return roleOf(me) === "manager";
}

export function isLibrarian(me) {
  return roleOf(me) === "librarian";
}

export function canManageUsers(me) {
  return isOwner(me) || isManager(me);
}

export function canManageGroupMemberships(me) {
  return canManageUsers(me);
}

export function canManageLibrary(me) {
  return isOwner(me) || isManager(me) || isLibrarian(me);
}

export function canAccessImports(me) {
  return canManageLibrary(me);
}

export function canCreateLibraryGroups(me) {
  return isOwner(me) || isManager(me);
}

export function hasCuratorMembership(me) {
  const groups = Array.isArray(me && me.groups) ? me.groups : [];
  return groups.some(
    (group) =>
      group &&
      group.is_curator === true &&
      group.is_public_group !== true
  );
}

export function canShowGroupsNav(me) {
  const groups = Array.isArray(me && me.groups) ? me.groups : [];
  return (
    groups.length > 0 ||
    canManageLibrary(me) ||
    canCreateLibraryGroups(me) ||
    canManageGroupMemberships(me) ||
    hasCuratorMembership(me)
  );
}

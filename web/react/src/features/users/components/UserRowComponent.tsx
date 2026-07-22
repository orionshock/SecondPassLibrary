import type { ManagedUser } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Badge } from "../../../components/ui";
import { displayUserRole } from "../../../domain/users/presentation";
import { usersEditBreadcrumbTrail } from "../usersBreadcrumbs";

export function UserRowComponent({ user, showGroups }: { user: ManagedUser; showGroups: boolean }) {
  const displayName = [user.firstName, user.lastName].filter(Boolean).join(" ") || "Not provided";
  const curates = user.groups.filter((group) => group.isCurator);

  return <tr className={`users-row${user.isActive ? "" : " users-row--inactive"}`}>
    <td><strong>{user.username}</strong>{user.mustChangePassword ? <span className="users-password-flag">Password change required</span> : null}</td>
    <td>{displayName}</td>
    <td className={user.email ? "" : "muted"}>{user.email || "No email"}</td>
    <td><Badge tone={user.isOwner ? "accent" : "default"}>{displayUserRole(user)}</Badge></td>
    <td><span className={`users-status-pill users-status-pill--${user.isActive ? "active" : "inactive"}`}>{user.isActive ? "Active" : "Inactive"}</span></td>
    <td className="users-last-login">{user.lastLogin ? new Date(user.lastLogin).toLocaleString() : "Never"}</td>
    {showGroups ? <td className="users-memberships">
      <div className="users-memberships__content">
        <span>{user.groups.length ? user.groups.map((group) => group.name).join(", ") : "None"}</span>
        {curates.length ? <span>Curates: {curates.map((group) => group.name).join(", ")}</span> : null}
      </div>
    </td> : null}
    <td className="users-row-actions">
      <Link className="icon-button" to={`/users/${encodeURIComponent(user.id)}/edit`} state={breadcrumbNavigationState(usersEditBreadcrumbTrail(user.username))} aria-label={`Edit ${user.username}`} title={`Edit ${user.username}`}>
        <MaterialIcon name="edit" />
      </Link>
    </td>
  </tr>;
}

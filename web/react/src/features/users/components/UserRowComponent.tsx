import type { ManagedUser } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Badge } from "../../../components/ui";
import { displayUserRole } from "../../../domain/users/presentation";
import { usersEditBreadcrumbTrail } from "../usersBreadcrumbs";

export function UserRowComponent({ user, showGroups }: { user: ManagedUser; showGroups: boolean }) {
  const displayName = [user.firstName, user.lastName].filter(Boolean).join(" ") || "Not provided";
  const memberships = user.groups.filter((group) => !group.isCurator);
  const curates = user.groups.filter((group) => group.isCurator);

  return <tr className={`users-row${user.isActive ? "" : " users-row--inactive"}`}>
    <td className="users-identity">
      <div className="users-identity__primary"><MaterialIcon name="person" size={16} /><strong>{displayName}</strong><span className="users-identity__dot" aria-hidden="true">•</span><span>{`<@${user.username}>`}</span></div>
      <div className={`users-identity__email${user.email ? "" : " muted"}`}>{user.email || "No email"}</div>
    </td>
    <td className="users-role-status"><div className="users-role-status__content"><Badge tone={user.isOwner ? "accent" : "default"}>{displayUserRole(user)}</Badge>{user.isActive ? null : <span className="users-status-pill users-status-pill--inactive">Inactive</span>}</div></td>
    <td className="users-last-login">{user.lastLogin ? new Date(user.lastLogin).toLocaleString() : "(never)"}</td>
    {showGroups ? <td className="users-memberships">
      <div className="users-memberships__content">
        <div className="users-memberships__stack" aria-label="Groups">
          {memberships.length ? memberships.map((group) => <Badge key={group.id} tone={group.isPublicGroup ? "success" : "default"}>
            {group.isPublicGroup ? <MaterialIcon name="public" size={15} /> : null}{group.name}
          </Badge>) : <span className="muted">(none)</span>}
        </div>
        <div className="users-memberships__stack" aria-label="Curates">
          {curates.length ? curates.map((group) => <Badge key={group.id} tone="accent">{group.name}</Badge>) : <span className="muted">(none)</span>}
        </div>
      </div>
    </td> : null}
    <td className="users-row-actions">
      <Link className="icon-button" to={`/users/${encodeURIComponent(user.id)}/edit`} state={breadcrumbNavigationState(usersEditBreadcrumbTrail(user.username))} aria-label={`Edit ${user.username}`} title={`Edit ${user.username}`}>
        <MaterialIcon name="edit" />
      </Link>
    </td>
  </tr>;
}

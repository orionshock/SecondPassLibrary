import { MaterialIcon } from "../../components/icons/MaterialIcon";
import "./UserInlineIdentityComponent.css";

export function UserInlineIdentityComponent({ username, displayName }: { username: string; displayName?: string }) {
  return <span className="user-inline-identity-component" aria-label={`User ${username}`}>
    <MaterialIcon name="person" size={15} />
    {displayName ? <><span className="user-inline-identity-component__display-name">{displayName}</span><span className="css-dot" aria-hidden="true" /></> : null}
    <span className="user-inline-identity-component__username">{username}</span>
  </span>;
}

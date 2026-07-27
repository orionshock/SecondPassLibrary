import { MaterialIcon } from "../../components/icons/MaterialIcon";
import "./UserInlineIdentityComponent.css";

export function UserInlineIdentityComponent({ username }: { username: string }) {
  return <span className="user-inline-identity-component" aria-label={`User ${username}`}>
    <MaterialIcon name="person" size={15} />
    <span>{username}</span>
  </span>;
}

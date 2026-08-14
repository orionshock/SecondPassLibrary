import { MaterialIcon } from "../../components/icons/MaterialIcon";
import { Badge } from "../../components/ui";
import "./GroupBadge.css";

export function GroupBadge({ name, isPublicGroup = false, size = "small" }: {
  name: string;
  isPublicGroup?: boolean;
  size?: "small" | "medium";
}) {
  return <span className={`group-badge-component group-badge-component--${size}`}><Badge tone={isPublicGroup ? "success" : "default"}>
    <span aria-label={`${isPublicGroup ? "Public group" : "Group"}: ${name}`}>
      <MaterialIcon name={isPublicGroup ? "public" : "group"} size={size === "medium" ? 18 : 15} />
      {name}
    </span>
  </Badge></span>;
}

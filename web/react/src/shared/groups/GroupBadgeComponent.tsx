import { MaterialIcon } from "../../components/icons/MaterialIcon";
import { Badge } from "../../components/ui";

export function GroupBadgeComponent({ name, isPublicGroup = false }: {
  name: string;
  isPublicGroup?: boolean;
}) {
  return <Badge tone={isPublicGroup ? "success" : "default"}>
    <span aria-label={`${isPublicGroup ? "Public group" : "Group"}: ${name}`}>
      <MaterialIcon name={isPublicGroup ? "public" : "group"} size={15} />
      {name}
    </span>
  </Badge>;
}

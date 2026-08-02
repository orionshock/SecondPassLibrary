import { Link } from "react-router";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";

export interface DashboardAction {
  to: string;
  label: string;
  icon: string;
  disabled?: boolean;
}

export function DashboardActionTileComponent({ action }: { action: DashboardAction }) {
  const content = <><MaterialIcon className="dashboard-action-tile__icon" name={action.icon} size="2rem" /><span>{action.label}</span></>;
  return action.disabled
    ? <span className="dashboard-action-tile" aria-disabled="true">{content}</span>
    : <Link className="dashboard-action-tile" to={action.to}>{content}</Link>;
}

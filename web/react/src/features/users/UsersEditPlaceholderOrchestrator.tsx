import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { PageHeader, Surface } from "../../components/ui";
import { usersEditBreadcrumbFallback } from "./usersBreadcrumbs";

export function UsersEditPlaceholderOrchestrator() {
  usePageBreadcrumbs(usersEditBreadcrumbFallback);
  return <div className="page-stack users-page">
    <PageHeader title="Edit user" />
    <Surface><p className="muted">User editing has not been rebuilt yet.</p></Surface>
  </div>;
}

import { Link } from "react-router-dom";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { marginaliaExportBreadcrumbFallback, marginaliaImportBreadcrumbFallback } from "../marginaliaBreadcrumbs";

export type MarginaliaSection = "sessions" | "import" | "export";

const sectionLinks = [
  { section: "sessions", label: "My Marginalia", icon: "history", to: "/marginalia" },
  { section: "import", label: "Import", icon: "upload_file", to: "/marginalia/import", state: breadcrumbNavigationState(marginaliaImportBreadcrumbFallback) },
  { section: "export", label: "Export", icon: "download", to: "/marginalia/export", state: breadcrumbNavigationState(marginaliaExportBreadcrumbFallback) },
] as const;

export function MarginaliaSectionActionsComponent({ activeSection }: { activeSection: MarginaliaSection }) {
  return <nav className="marginalia-section-actions" aria-label="My Marginalia sections">
    {sectionLinks.map((link) => <Link
      key={link.section}
      className="button button--primary"
      to={link.to}
      state={"state" in link ? link.state : undefined}
      aria-current={link.section === activeSection ? "page" : undefined}
    ><MaterialIcon name={link.icon} /><span>{link.label}</span></Link>)}
  </nav>;
}

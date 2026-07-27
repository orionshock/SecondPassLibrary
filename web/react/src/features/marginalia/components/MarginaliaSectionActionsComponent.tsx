import { Link } from "react-router-dom";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { marginaliaExportBreadcrumbFallback, marginaliaImportBreadcrumbFallback } from "../marginaliaBreadcrumbs";

export type MarginaliaSection = "sessions" | "import" | "export";

const sectionLinks = [
  { section: "sessions", label: "My Marginalia", to: "/marginalia" },
  { section: "import", label: "Import", to: "/marginalia/import", state: breadcrumbNavigationState(marginaliaImportBreadcrumbFallback) },
  { section: "export", label: "Export", to: "/marginalia/export", state: breadcrumbNavigationState(marginaliaExportBreadcrumbFallback) },
] as const;

export function MarginaliaSectionActionsComponent({ activeSection }: { activeSection: MarginaliaSection }) {
  return <nav className="marginalia-section-actions" aria-label="My Marginalia sections">
    {sectionLinks.map((link) => <Link
      key={link.section}
      className="button button--primary"
      to={link.to}
      state={"state" in link ? link.state : undefined}
      aria-current={link.section === activeSection ? "page" : undefined}
    >{link.label}</Link>)}
  </nav>;
}

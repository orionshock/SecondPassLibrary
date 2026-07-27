import { Link } from "react-router-dom";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { readingExportBreadcrumbFallback, readingImportBreadcrumbFallback } from "../readingBreadcrumbs";

export type ReadingSection = "sessions" | "import" | "export";

const sectionLinks = [
  { section: "sessions", label: "My Marginalia", to: "/reading" },
  { section: "import", label: "Import", to: "/reading/import", state: breadcrumbNavigationState(readingImportBreadcrumbFallback) },
  { section: "export", label: "Export", to: "/reading/export", state: breadcrumbNavigationState(readingExportBreadcrumbFallback) },
] as const;

export function ReadingSectionActionsComponent({ activeSection }: { activeSection: ReadingSection }) {
  return <nav className="reading-section-actions" aria-label="My Marginalia sections">
    {sectionLinks.map((link) => <Link
      key={link.section}
      className="button button--primary"
      to={link.to}
      state={"state" in link ? link.state : undefined}
      aria-current={link.section === activeSection ? "page" : undefined}
    >{link.label}</Link>)}
  </nav>;
}

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { PageHeader } from "../../components/ui";

const fallback = [{ label: "Library", to: "/library" }, { label: "Book" }] as const;

export function BookDetailPlaceholderOrchestrator() {
  usePageBreadcrumbs(fallback);
  return <div className="page-stack library-page">
    <PageHeader title="Book" />
    <section className="page-panel">
      <p>Book detail is not rebuilt yet.</p>
    </section>
  </div>;
}

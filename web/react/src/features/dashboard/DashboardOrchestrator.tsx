import { PageHeader, Surface } from "../../components/ui";

export function DashboardOrchestrator() {
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Dashboard"
        title="Your reading home"
        description="The React dashboard foundation is ready for its future reading and library regions."
      />
      <Surface title="Dashboard preview">
        <p className="muted">Metrics, recent reading, and activity have not been rebuilt yet.</p>
      </Surface>
    </div>
  );
}

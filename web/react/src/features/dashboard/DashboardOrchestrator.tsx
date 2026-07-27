import { Surface } from "../../components/ui";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";

export function DashboardOrchestrator() {
  return (
    <ProductPageShellComponent
      eyebrow="Dashboard"
      title="Your reading home"
      description="The React dashboard foundation is ready for its future reading and library regions."
    >
      <Surface title="Dashboard preview">
        <p className="muted">Metrics, recent reading, and activity have not been rebuilt yet.</p>
      </Surface>
    </ProductPageShellComponent>
  );
}

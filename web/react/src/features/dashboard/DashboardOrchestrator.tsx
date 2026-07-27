import { useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { Surface } from "../../components/ui";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";
import "./Dashboard.css";

export function DashboardOrchestrator() {
  const { currentUser } = useOutletContext<AppOutletContext>();

  return (
    <ProductPageShellComponent
      eyebrow="Dashboard"
      title="Your reading home"
      description="The React dashboard foundation is ready for its future reading and library regions."
    >
      {currentUser.bannerText ? <aside className="dashboard-banner">{currentUser.bannerText}</aside> : null}
      <Surface title="Dashboard preview">
        <p className="muted">Metrics, recent reading, and activity have not been rebuilt yet.</p>
      </Surface>
    </ProductPageShellComponent>
  );
}

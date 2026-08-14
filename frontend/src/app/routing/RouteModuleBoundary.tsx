import { Component, type ReactNode } from "react";

import { Button, ErrorPanel } from "../../components/ui";

export function RouteModuleLoading() {
  return <section className="page-panel" data-route-state="loading" aria-live="polite" aria-busy="true">
    <p>Loading page...</p>
  </section>;
}

export function RouteModuleError({ onReload }: { onReload: () => void }) {
  return <section className="page-panel" data-route-state="error">
    <ErrorPanel>Unable to load this page.</ErrorPanel>
    <Button type="button" tone="secondary" onClick={onReload}>Reload page</Button>
  </section>;
}

export class RouteModuleBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return <RouteModuleError onReload={() => window.location.reload()} />;
    }
    return this.props.children;
  }
}

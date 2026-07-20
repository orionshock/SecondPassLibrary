import type { ReactNode } from "react";

import { PageHeader, Surface } from "../../../components/ui";

export function PairingPageFrameComponent({ children }: { children: ReactNode }) {
  return <div className="page-stack account-page">
    <PageHeader title="Authorize reader/client" />
    <Surface title="Client API">{children}</Surface>
  </div>;
}

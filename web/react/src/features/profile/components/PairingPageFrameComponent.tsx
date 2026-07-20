import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { PageHeader, Surface } from "../../../components/ui";

export function PairingPageFrameComponent({ children }: { children: ReactNode }) {
  return <div className="page-stack account-page">
    <nav className="breadcrumbs" aria-label="Breadcrumb"><Link to="/profile">Profile</Link><span aria-hidden="true">/</span><span>Authorize Reader Client</span></nav>
    <PageHeader title="Authorize reader/client" />
    <Surface title="Client API">{children}</Surface>
  </div>;
}

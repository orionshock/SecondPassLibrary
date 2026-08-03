import type { ReactNode } from "react";

import { Surface } from "../../../components/ui";
import { ProductPageShellComponent } from "../../../shared/layout/ProductPageShellComponent";

export function PairingPageFrameComponent({ children }: { children: ReactNode }) {
  return <ProductPageShellComponent className="account-page" title="Authorize reader/client">
    <Surface title="Client API">{children}</Surface>
  </ProductPageShellComponent>;
}

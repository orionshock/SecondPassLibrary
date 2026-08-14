import type { ReactNode } from "react";

import { Surface } from "../../../components/ui";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";

export function PairingPageFrame({ children }: { children: ReactNode }) {
  return <ProductPageShell className="account-page" title="Authorize reader/client">
    <Surface title="Client API">{children}</Surface>
  </ProductPageShell>;
}

import { appendBreadcrumbTrail, type BreadcrumbItem } from "../../app/navigation/breadcrumbs";

export const profileBreadcrumbFallback: readonly BreadcrumbItem[] = [];

const profileParentTrail: readonly BreadcrumbItem[] = [{ label: "Profile", to: "/profile" }];

export const passwordBreadcrumbFallback: readonly BreadcrumbItem[] = appendBreadcrumbTrail(
  profileParentTrail,
  { label: "Password" },
);

export const clientPairingBreadcrumbFallback: readonly BreadcrumbItem[] = appendBreadcrumbTrail(
  profileParentTrail,
  { label: "Client pairing" },
);

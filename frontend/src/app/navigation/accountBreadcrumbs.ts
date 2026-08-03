import { appendBreadcrumbTrail, type BreadcrumbItem } from "./breadcrumbs";

export const profileBreadcrumbFallback: readonly BreadcrumbItem[] = [];

const profileParentTrail: readonly BreadcrumbItem[] = [{ label: "Profile", to: "/profile", resetTrail: true, icon: "profile" }];

export const passwordBreadcrumbFallback: readonly BreadcrumbItem[] = appendBreadcrumbTrail(
  profileParentTrail,
  { label: "Password" },
);

export const clientPairingBreadcrumbFallback: readonly BreadcrumbItem[] = appendBreadcrumbTrail(
  profileParentTrail,
  { label: "Client pairing" },
);

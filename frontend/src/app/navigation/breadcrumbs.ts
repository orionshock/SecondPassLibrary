export type BreadcrumbIcon =
  | "library"
  | "book"
  | "author"
  | "series"
  | "catalog-tag"
  | "group"
  | "public-group"
  | "shelf"
  | "shared-shelf"
  | "group-shelf"
  | "user"
  | "profile"
  | "server-settings"
  | "import";

export interface BreadcrumbItem {
  label: string;
  to?: string;
  resetTrail?: boolean;
  icon?: BreadcrumbIcon;
}

export const breadcrumbIconSymbols: Readonly<Record<BreadcrumbIcon, string>> = {
  library: "local_library",
  book: "menu_book",
  author: "person",
  series: "auto_stories",
  "catalog-tag": "sell",
  group: "group",
  "public-group": "public",
  shelf: "shelves",
  "shared-shelf": "share",
  "group-shelf": "group_work",
  user: "person",
  profile: "account_circle",
  "server-settings": "settings",
  import: "upload_file",
};

export interface BreadcrumbLocationState {
  breadcrumbTrail: BreadcrumbItem[];
  breadcrumbContextId: string;
}

const maximumTrailLength = 12;
const maximumLabelLength = 160;
const maximumPathLength = 2048;
const runtimeBreadcrumbContextId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;

export function appendBreadcrumbTrail(parent: readonly BreadcrumbItem[], item: BreadcrumbItem): BreadcrumbItem[] {
  const trail = [...parent, item];
  if (trail.length <= maximumTrailLength) return trail;
  return [trail[0]!, ...trail.slice(-(maximumTrailLength - 1))];
}

export function breadcrumbNavigationState(trail: readonly BreadcrumbItem[]): BreadcrumbLocationState {
  return {
    breadcrumbTrail: trail.map(({ label, to, resetTrail, icon }) => ({
      label,
      ...(to ? { to } : {}),
      ...(resetTrail ? { resetTrail: true } : {}),
      ...(icon ? { icon } : {}),
    })),
    breadcrumbContextId: runtimeBreadcrumbContextId,
  };
}

export function breadcrumbLinkState(items: readonly BreadcrumbItem[], index: number): BreadcrumbLocationState | undefined {
  if (items[index]?.resetTrail) return undefined;
  return breadcrumbNavigationState(items.slice(0, index + 1).map(({ label, to, icon }) => ({
    label,
    ...(to ? { to } : {}),
    ...(icon ? { icon } : {}),
  })));
}

export function readIncomingBreadcrumbTrail(state: unknown): BreadcrumbItem[] | undefined {
  if (!isRecord(state) || state.breadcrumbContextId !== runtimeBreadcrumbContextId || !Array.isArray(state.breadcrumbTrail)) return undefined;
  if (state.breadcrumbTrail.length === 0 || state.breadcrumbTrail.length > maximumTrailLength) return undefined;

  const trail: BreadcrumbItem[] = [];
  for (const value of state.breadcrumbTrail) {
    const item = readBreadcrumbItem(value);
    if (!item) return undefined;
    trail.push(item);
  }
  return trail;
}

export function resolveBreadcrumbTrail(
  state: unknown,
  fallback: readonly BreadcrumbItem[],
  suppress = false,
): BreadcrumbItem[] {
  if (suppress) return [];
  return readIncomingBreadcrumbTrail(state) ?? fallback.map(({ label, to, resetTrail, icon }) => ({
    label,
    ...(to ? { to } : {}),
    ...(resetTrail ? { resetTrail: true } : {}),
    ...(icon ? { icon } : {}),
  }));
}

function readBreadcrumbItem(value: unknown): BreadcrumbItem | undefined {
  if (!isRecord(value) || typeof value.label !== "string") return undefined;
  const label = value.label.trim();
  if (!label || label.length > maximumLabelLength) return undefined;
  if (value.resetTrail !== undefined && value.resetTrail !== true) return undefined;
  const resetTrail = value.resetTrail === true;
  if (value.icon !== undefined && !isBreadcrumbIcon(value.icon)) return undefined;
  const icon = value.icon as BreadcrumbIcon | undefined;
  if (value.to === undefined) return { label, ...(resetTrail ? { resetTrail: true } : {}), ...(icon ? { icon } : {}) };
  if (typeof value.to !== "string" || !isInternalPath(value.to)) return undefined;
  return { label, to: value.to, ...(resetTrail ? { resetTrail: true } : {}), ...(icon ? { icon } : {}) };
}

function isBreadcrumbIcon(value: unknown): value is BreadcrumbIcon {
  return typeof value === "string" && Object.hasOwn(breadcrumbIconSymbols, value);
}

function isInternalPath(value: string): boolean {
  return value.length <= maximumPathLength && /^\/(?!\/)[^\u0000-\u001f]*$/.test(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

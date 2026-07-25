export interface BreadcrumbItem {
  label: string;
  to?: string;
  resetTrail?: boolean;
}

export interface BreadcrumbLocationState {
  breadcrumbTrail: BreadcrumbItem[];
  breadcrumbContextId: string;
}

const maximumTrailLength = 12;
const maximumLabelLength = 160;
const maximumPathLength = 2048;
const runtimeBreadcrumbContextId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;

export function appendBreadcrumbTrail(parent: readonly BreadcrumbItem[], item: BreadcrumbItem): BreadcrumbItem[] {
  return [...parent, item];
}

export function breadcrumbNavigationState(trail: readonly BreadcrumbItem[]): BreadcrumbLocationState {
  return {
    breadcrumbTrail: trail.map(({ label, to, resetTrail }) => ({
      label,
      ...(to ? { to } : {}),
      ...(resetTrail ? { resetTrail: true } : {}),
    })),
    breadcrumbContextId: runtimeBreadcrumbContextId,
  };
}

export function breadcrumbLinkState(items: readonly BreadcrumbItem[], index: number): BreadcrumbLocationState | undefined {
  if (items[index]?.resetTrail) return undefined;
  return breadcrumbNavigationState(items.slice(0, index + 1).map(({ label, to }) => ({ label, ...(to ? { to } : {}) })));
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
  return readIncomingBreadcrumbTrail(state) ?? fallback.map(({ label, to, resetTrail }) => ({
    label,
    ...(to ? { to } : {}),
    ...(resetTrail ? { resetTrail: true } : {}),
  }));
}

function readBreadcrumbItem(value: unknown): BreadcrumbItem | undefined {
  if (!isRecord(value) || typeof value.label !== "string") return undefined;
  const label = value.label.trim();
  if (!label || label.length > maximumLabelLength) return undefined;
  if (value.resetTrail !== undefined && value.resetTrail !== true) return undefined;
  const resetTrail = value.resetTrail === true;
  if (value.to === undefined) return { label, ...(resetTrail ? { resetTrail: true } : {}) };
  if (typeof value.to !== "string" || !isInternalPath(value.to)) return undefined;
  return { label, to: value.to, ...(resetTrail ? { resetTrail: true } : {}) };
}

function isInternalPath(value: string): boolean {
  return value.length <= maximumPathLength && /^\/(?!\/)[^\u0000-\u001f]*$/.test(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

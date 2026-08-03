export interface ResolvedTabQuery<T extends string> {
  tab: T;
  needsCanonicalReplace: boolean;
}

export function resolveTabQuery<T extends string>(
  parameters: URLSearchParams,
  knownTabs: readonly T[],
  defaultTab: T,
): ResolvedTabQuery<T> {
  const requested = parameters.get("tab");
  if (requested === null) return { tab: defaultTab, needsCanonicalReplace: false };
  if (knownTabs.includes(requested as T)) {
    return {
      tab: requested as T,
      needsCanonicalReplace: requested === defaultTab,
    };
  }
  return { tab: defaultTab, needsCanonicalReplace: true };
}

export function withTabQuery<T extends string>(
  parameters: URLSearchParams,
  tab: T,
  defaultTab: T,
): URLSearchParams {
  const next = new URLSearchParams(parameters);
  if (tab === defaultTab) next.delete("tab");
  else next.set("tab", tab);
  return next;
}

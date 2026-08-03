import { resolveTabQuery, withTabQuery } from "../../app/routing/tabQuery";

export type BookDetailTab = "shelves" | "groups" | "metadata";
export type BookEditTab = "book" | "catalog" | "authors-series" | "groups" | "group-shelves" | "identifiers";

export interface BookTabQueryState<T extends string> {
  tab: T;
  query: string;
}

const bookDetailTabs: readonly BookDetailTab[] = ["shelves", "groups", "metadata"];
const simpleBookDetailTabs: readonly BookDetailTab[] = ["shelves", "metadata"];
const bookEditTabs: readonly BookEditTab[] = ["book", "catalog", "authors-series", "groups", "group-shelves", "identifiers"];
const simpleBookEditTabs: readonly BookEditTab[] = ["book", "catalog", "authors-series", "group-shelves", "identifiers"];

export function bookDetailQueryFromSearchParams(
  parameters: URLSearchParams,
  groupsEnabled: boolean,
): BookTabQueryState<BookDetailTab> {
  const knownTabs = groupsEnabled ? bookDetailTabs : simpleBookDetailTabs;
  const { tab } = resolveTabQuery(parameters, knownTabs, "shelves");
  return { tab, query: withTabQuery(parameters, tab, "shelves").toString() };
}

export function bookDetailSearchParams(
  parameters: URLSearchParams,
  tab: BookDetailTab,
): URLSearchParams {
  return withTabQuery(parameters, tab, "shelves");
}

export function bookEditQueryFromSearchParams(
  parameters: URLSearchParams,
  groupsEnabled: boolean,
): BookTabQueryState<BookEditTab> {
  const knownTabs = groupsEnabled ? bookEditTabs : simpleBookEditTabs;
  const { tab } = resolveTabQuery(parameters, knownTabs, "book");
  return { tab, query: withTabQuery(parameters, tab, "book").toString() };
}

export function bookEditSearchParams(
  parameters: URLSearchParams,
  tab: BookEditTab,
): URLSearchParams {
  return withTabQuery(parameters, tab, "book");
}

export function bookEditQueryDuringImmediateMutation(
  requested: BookTabQueryState<BookEditTab>,
  stable: BookTabQueryState<BookEditTab>,
  pending: boolean,
): BookTabQueryState<BookEditTab> {
  return pending ? stable : requested;
}

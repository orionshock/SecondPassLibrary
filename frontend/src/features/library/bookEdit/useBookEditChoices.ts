import {
  listAuthors,
  listCatalogTags,
  listGroups,
  listSeries,
  type BookAuthorSummary,
  type BookDetail,
  type BookGroupSummary,
  type BookSeriesSummary,
  type CatalogTag,
  type CatalogTagSummary,
  type LibraryAuthor,
  type LibraryGroup,
  type LibrarySeries,
} from "@second-pass/spl-api";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { normalizeMutationError } from "../../../shared/feedback/mutationState";
import type { BookEditTab } from "../bookTabs";

const BOOK_EDIT_CHOICE_PAGE_SIZE = 25;

export type BookEditAuthorChoice = BookAuthorSummary | LibraryAuthor;
export type BookEditSeriesChoice = BookSeriesSummary | LibrarySeries;
export type BookEditTagChoice = CatalogTagSummary | CatalogTag;
export type BookEditGroupChoice = BookGroupSummary | LibraryGroup;

interface BookEditChoiceState<T> {
  query: string;
  items: T[];
  loading: boolean;
  error?: Error;
  setQuery: (query: string) => void;
  retry: () => void;
}

type Choice = { id: string };
type ChoiceRequest<T extends Choice> = (query: string) => Promise<T[]>;

const searchAuthors: ChoiceRequest<LibraryAuthor> = async (query) => (
  await listAuthors({ q: query || undefined, ordering: "name", pageSize: BOOK_EDIT_CHOICE_PAGE_SIZE })
).items;
const searchSeries: ChoiceRequest<LibrarySeries> = async (query) => (
  await listSeries({ q: query || undefined, ordering: "name", pageSize: BOOK_EDIT_CHOICE_PAGE_SIZE })
).items;
const searchTags: ChoiceRequest<CatalogTag> = async (query) => (
  await listCatalogTags({ q: query || undefined, ordering: "name", pageSize: BOOK_EDIT_CHOICE_PAGE_SIZE })
).items;
const searchGroups: ChoiceRequest<LibraryGroup> = async (query) => (
  await listGroups({ q: query || undefined, ordering: "name", pageSize: BOOK_EDIT_CHOICE_PAGE_SIZE })
).items;

export function useBookEditChoices({
  book,
  tab,
  canEditGroups,
  selectedAuthorIds,
  selectedSeriesId,
}: {
  book?: BookDetail;
  tab: BookEditTab;
  canEditGroups: boolean;
  selectedAuthorIds: readonly string[];
  selectedSeriesId: string | null;
}) {
  const lifetime = book?.id;
  const authorSeeds = useMemo(() => book?.authors ?? [], [book?.authors]);
  const seriesSeeds = useMemo(() => book?.series ? [book.series] : [], [book?.series]);
  const tagSeeds = useMemo(() => book?.catalogTags ?? [], [book?.catalogTags]);
  const groupSeeds = useMemo(() => book?.groups ?? [], [book?.groups]);

  const authors = useChoiceSearch(
    tab === "authors-series" && Boolean(book),
    lifetime,
    authorSeeds,
    selectedAuthorIds,
    searchAuthors,
  );
  const series = useChoiceSearch(
    tab === "authors-series" && Boolean(book),
    lifetime,
    seriesSeeds,
    selectedSeriesId ? [selectedSeriesId] : [],
    searchSeries,
  );
  const tags = useChoiceSearch(
    tab === "catalog" && Boolean(book),
    lifetime,
    tagSeeds,
    tagSeeds.map(({ id }) => id),
    searchTags,
  );
  const groups = useChoiceSearch(
    tab === "groups" && canEditGroups && Boolean(book),
    lifetime,
    groupSeeds,
    groupSeeds.map(({ id }) => id),
    searchGroups,
  );
  return { authors, series, tags, groups };
}

function useChoiceSearch<T extends Choice, S extends Choice>(
  enabled: boolean,
  lifetime: string | undefined,
  seeds: readonly S[],
  selectedIds: readonly string[],
  request: ChoiceRequest<T>,
): BookEditChoiceState<T | S> {
  const [query, setQuery] = useState("");
  const [retryRevision, setRetryRevision] = useState(0);
  const [result, setResult] = useState<{ items: T[]; loading: boolean; error?: Error }>({
    items: [],
    loading: false,
  });
  const requestRevision = useRef(0);
  const knownChoices = useRef(new Map<string, T | S>());
  const selectedIdsRef = useRef(selectedIds);
  selectedIdsRef.current = selectedIds;

  useLayoutEffect(() => {
    requestRevision.current += 1;
    knownChoices.current = new Map(seeds.map((item) => [item.id, item]));
    setResult({ items: [], loading: false });
  }, [lifetime, seeds]);

  useEffect(() => {
    const revision = ++requestRevision.current;
    if (!enabled || !lifetime) return;
    setResult((current) => ({ ...current, loading: true, error: undefined }));
    request(query.trim()).then((items) => {
      if (requestRevision.current !== revision) return;
      const nextKnownChoices = new Map<string, T | S>(seeds.map((item) => [item.id, item]));
      for (const id of selectedIdsRef.current) {
        const selected = knownChoices.current.get(id);
        if (selected) nextKnownChoices.set(id, selected);
      }
      for (const item of items) nextKnownChoices.set(item.id, item);
      knownChoices.current = nextKnownChoices;
      setResult({ items, loading: false });
    }).catch((error: unknown) => {
      if (requestRevision.current !== revision) return;
      setResult((current) => ({
        ...current,
        loading: false,
        error: normalizeMutationError(error),
      }));
    });
    return () => { requestRevision.current += 1; };
  }, [enabled, lifetime, query, request, retryRevision]);

  const items = mergeChoices(
    selectedIds.map((id) => knownChoices.current.get(id)).filter(isChoice),
    seeds,
    result.items,
  );
  return {
    query,
    items,
    loading: result.loading,
    error: result.error,
    setQuery,
    retry: () => setRetryRevision((value) => value + 1),
  };
}

function mergeChoices<T extends Choice>(...groups: readonly (readonly T[])[]): T[] {
  const merged = new Map<string, T>();
  for (const group of groups) {
    for (const item of group) merged.set(item.id, item);
  }
  return [...merged.values()];
}

function isChoice<T>(choice: T | undefined): choice is T {
  return choice !== undefined;
}

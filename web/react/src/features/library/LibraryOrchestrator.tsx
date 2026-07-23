import {
  ApiError,
  listAllCatalogTags,
  listBooks,
  type CatalogTag,
  type CompactBook,
  type LibraryBooksQuery,
  type Page,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { PageHeader } from "../../components/ui";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { libraryBooksSdkQuery, libraryPath, librarySearchParams, libraryStateFromSearchParams, withLibraryChange } from "./libraryQuery";
import { BookListPageRegion } from "./regions/BookListPageRegion";
import { CatalogTagRailPageRegion } from "./regions/CatalogTagRailPageRegion";
import { LibraryBooksControlsPageRegion } from "./regions/LibraryBooksControlsPageRegion";
import "./Library.css";

interface BooksLoadState {
  page?: Page<CompactBook>;
  loading: boolean;
  error?: Error;
}

interface TagsLoadState {
  tags?: CatalogTag[];
  loading: boolean;
  error?: Error;
}

export const libraryBreadcrumbFallback = [] as const;

export function LibraryOrchestrator() {
  usePageBreadcrumbs(libraryBreadcrumbFallback);
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(() => libraryStateFromSearchParams(new URLSearchParams(queryKey)), [queryKey]);
  const canonicalQuery = librarySearchParams(queryState).toString();
  const [searchDraft, setSearchDraft] = useState(queryState.q);
  const [bookRetry, setBookRetry] = useState(0);
  const [tagRetry, setTagRetry] = useState(0);
  const [books, setBooks] = useState<BooksLoadState>({ loading: true });
  const [tags, setTags] = useState<TagsLoadState>({ loading: true });

  useEffect(() => setSearchDraft(queryState.q), [queryState.q]);

  useEffect(() => {
    if (queryKey === canonicalQuery) return;
    setSearchParameters(new URLSearchParams(canonicalQuery), { replace: true });
  }, [canonicalQuery, queryKey, setSearchParameters]);

  useEffect(() => {
    let active = true;
    setTags((current) => ({ tags: current.tags, loading: true }));
    listAllCatalogTags()
      .then((loadedTags) => { if (active) setTags({ tags: loadedTags, loading: false }); })
      .catch((error: unknown) => { if (active) setTags((current) => ({ tags: current.tags, loading: false, error: normalizeMutationError(error) })); });
    return () => { active = false; };
  }, [tagRetry]);

  useEffect(() => {
    if (!queryState.tag || !tags.tags || tags.tags.some(({ slug }) => slug === queryState.tag)) return;
    changeQuery({ tag: undefined });
  }, [queryState.tag, tags.tags]);

  useEffect(() => {
    if (queryKey !== canonicalQuery) return;
    let active = true;
    setBooks((current) => ({ page: current.page, loading: true }));
    loadBooksWithPageRecovery(libraryBooksSdkQuery(queryState))
      .then(({ page, correctedPage }) => {
        if (!active) return;
        if (correctedPage !== queryState.page) {
          setSearchParameters(librarySearchParams(withLibraryChange(queryState, { page: correctedPage }, false)), { replace: true });
          return;
        }
        setBooks({ page, loading: false });
      })
      .catch((error: unknown) => { if (active) setBooks((current) => ({ page: current.page, loading: false, error: normalizeMutationError(error) })); });
    return () => { active = false; };
  }, [bookRetry, canonicalQuery, queryKey, queryState.ordering, queryState.page, queryState.pageSize, queryState.q, queryState.tag, setSearchParameters]);

  function changeQuery(changes: Parameters<typeof withLibraryChange>[1], resetPage = true) {
    setSearchParameters(librarySearchParams(withLibraryChange(queryState, changes, resetPage)));
  }

  return <div className="page-stack library-page">
    <PageHeader title="Library" />
    <LibraryBooksControlsPageRegion
      search={searchDraft}
      ordering={queryState.ordering}
      onSearchChange={setSearchDraft}
      onSearch={() => changeQuery({ q: searchDraft.trim() })}
      onOrderingChange={(ordering) => changeQuery({ ordering })}
    />
    <div className="library-browser">
      <CatalogTagRailPageRegion
        tags={tags.tags}
        activeTag={queryState.tag}
        loading={tags.loading}
        error={tags.error}
        onTagChange={(tag) => changeQuery({ tag })}
        onRetry={() => setTagRetry((value) => value + 1)}
      />
      <BookListPageRegion
        page={books.page}
        pageNumber={queryState.page}
        pageSize={queryState.pageSize}
        loading={books.loading}
        error={books.error}
        libraryPath={libraryPath(queryState)}
        onPageChange={(page) => changeQuery({ page }, false)}
        onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
        onRetry={() => setBookRetry((value) => value + 1)}
      />
    </div>
  </div>;
}

export async function loadBooksWithPageRecovery(
  query: LibraryBooksQuery,
  request: (query: LibraryBooksQuery) => Promise<Page<CompactBook>> = listBooks,
): Promise<{ page: Page<CompactBook>; correctedPage: number }> {
  const requestedPage = query.page ?? 1;
  try {
    return { page: await request(query), correctedPage: requestedPage };
  } catch (error) {
    if (requestedPage <= 1 || !(error instanceof ApiError) || error.status !== 404) throw error;
    const firstPage = await request({ ...query, page: 1 });
    const maxPage = Math.max(1, Math.ceil(firstPage.count / (query.pageSize ?? 20)));
    if (maxPage === 1) return { page: firstPage, correctedPage: 1 };
    return { page: await request({ ...query, page: maxPage }), correctedPage: maxPage };
  }
}

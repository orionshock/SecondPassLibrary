import {
  ApiError,
  getAuthor,
  getSeries,
  isAtLeastLibrarian,
  listAllCatalogTags,
  listAuthors,
  listBooks,
  listSeries,
  type CatalogTag,
  type CompactBook,
  type LibraryAuthor,
  type LibrarySeries,
  type Page,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useOutletContext, useSearchParams } from "react-router";

import type { AppOutletContext } from "../../../app/layout/AppOrchestrator";
import { usePageBreadcrumbs } from "../../../app/navigation/usePageBreadcrumbs";
import { loadPageWithRecovery } from "../../../app/routing/pageRecovery";
import { normalizeMutationError } from "../../../shared/feedback/mutationState";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import {
  libraryAxisBasePath,
  libraryAxisSdkQuery,
  libraryBooksSdkQuery,
  libraryPath,
  libraryRequestView,
  librarySearchParams,
  libraryStateFromSearchParams,
  withLibraryChange,
  withLibrarySelectedContext,
  type LibraryUrlState,
  type LibraryView,
} from "../libraryQuery";
import { readSelectedLibraryContextDisplay } from "../libraryPresentation";
import { AuthorListPageRegion } from "./AuthorListPageRegion";
import { BookListPageRegion } from "./BookListPageRegion";
import { CatalogBrowserPageRegion } from "./CatalogBrowserPageRegion";
import { CatalogTagRailPageRegion } from "./CatalogTagRailPageRegion";
import "./Library.css";
import { LibraryAxesPageRegion } from "./LibraryAxesPageRegion";
import { LibraryAxisControlsPageRegion } from "./LibraryAxisControlsPageRegion";
import { SelectedLibraryContextPageRegion } from "./SelectedLibraryContextPageRegion";
import { SeriesListPageRegion } from "./SeriesListPageRegion";

interface LoadState<Item> {
  page?: Page<Item>;
  loading: boolean;
  error?: Error;
}

interface TagsLoadState {
  tags?: CatalogTag[];
  loading: boolean;
  error?: Error;
}

export interface SelectedLibraryContextDetails {
  kind: "author" | "series";
  id: string;
  name: string;
  bookCount: number;
  blurb: string;
}

type SelectedContextDetailsLoad =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; details: SelectedLibraryContextDetails }
  | { status: "unavailable" }
  | { status: "error"; error: Error };

export const libraryBreadcrumbFallback = [] as const;

export function LibraryOrchestrator() {
  usePageBreadcrumbs(libraryBreadcrumbFallback);
  const { currentUser } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(() => libraryStateFromSearchParams(new URLSearchParams(queryKey)), [queryKey]);
  const selectedContextKind = queryState.authorId ? "author" : queryState.seriesId ? "series" : undefined;
  const requestView = libraryRequestView(queryState);
  const selectedContextDisplay = useMemo(
    () => readSelectedLibraryContextDisplay(location.state, queryState),
    [location.state, queryState],
  );
  const canonicalQuery = librarySearchParams(queryState).toString();
  const [searchDraft, setSearchDraft] = useState(queryState.q);
  const [listRetry, setListRetry] = useState(0);
  const [tagRetry, setTagRetry] = useState(0);
  const [contextRetry, setContextRetry] = useState(0);
  const [books, setBooks] = useState<LoadState<CompactBook>>({ loading: true });
  const [authors, setAuthors] = useState<LoadState<LibraryAuthor>>({ loading: true });
  const [series, setSeries] = useState<LoadState<LibrarySeries>>({ loading: true });
  const [tags, setTags] = useState<TagsLoadState>({ loading: false });
  const [contextDetails, setContextDetails] = useState<SelectedContextDetailsLoad>({ status: "idle" });
  const recoveredPageKeys = useRef(new Set<string>());

  useEffect(() => setSearchDraft(queryState.q), [queryState.authorId, queryState.q, queryState.seriesId, queryState.view]);

  useEffect(() => {
    if (queryKey === canonicalQuery) return;
    setSearchParameters(new URLSearchParams(canonicalQuery), { replace: true, state: selectedContextDisplay ? location.state : null });
  }, [canonicalQuery, location.state, queryKey, selectedContextDisplay, setSearchParameters]);

  useEffect(() => {
    if (tags.tags) return;
    let active = true;
    setTags({ loading: true });
    listAllCatalogTags()
      .then((loadedTags) => { if (active) setTags({ tags: loadedTags, loading: false }); })
      .catch((error: unknown) => { if (active) setTags({ loading: false, error: normalizeMutationError(error) }); });
    return () => { active = false; };
  }, [tagRetry, tags.tags]);

  useEffect(() => {
    const id = queryState.authorId ?? queryState.seriesId;
    if (!selectedContextKind || !id) {
      setContextDetails({ status: "idle" });
      return;
    }
    let active = true;
    setContextDetails({ status: "loading" });
    loadSelectedLibraryContextDetails(selectedContextKind, id)
      .then((details) => { if (active) setContextDetails({ status: "ready", details }); })
      .catch((error: unknown) => {
        if (!active) return;
        setContextDetails(error instanceof ApiError && error.status === 404
          ? { status: "unavailable" }
          : { status: "error", error: normalizeMutationError(error) });
      });
    return () => { active = false; };
  }, [contextRetry, queryState.authorId, queryState.seriesId, selectedContextKind]);

  useEffect(() => {
    if (!unknownCatalogTag(queryState.tag, tags.tags)) return;
    changeQuery({ tag: undefined });
  }, [queryState.tag, tags.tags]);

  useEffect(() => {
    if (queryKey !== canonicalQuery) return;
    let active = true;
    const locationState = location.state;

    const recoverPage = <Item,>(request: (page: number) => Promise<Page<Item>>) => loadPageWithRecovery({
      requestedPage: queryState.page,
      pageSize: queryState.pageSize,
      recoveryKey: `${requestView}:${canonicalQuery}`,
      recoveredKeys: recoveredPageKeys.current,
      fetchPage: request,
      buildRecoveredLocation: (page) => librarySearchParams(withLibraryChange(queryState, { page }, false)).toString(),
      replaceLocation: (location) => {
        if (!active) return false;
        setSearchParameters(new URLSearchParams(location), { replace: true, state: selectedContextDisplay ? locationState : null });
        return true;
      },
    });

    if (requestView === "books") {
      setBooks((current) => ({ page: current.page, loading: true }));
      const sdkQuery = libraryBooksSdkQuery(queryState);
      recoverPage((page) => listBooks({ ...sdkQuery, page }))
        .then(({ page, recovered }) => {
          if (!active) return;
          if (recovered) return;
          setBooks({ page, loading: false });
        })
        .catch((error: unknown) => { if (active) setBooks((current) => ({ page: current.page, loading: false, error: normalizeMutationError(error) })); });
    } else if (requestView === "authors") {
      setAuthors((current) => ({ page: current.page, loading: true }));
      const sdkQuery = libraryAxisSdkQuery(queryState);
      recoverPage((page) => listAuthors({ ...sdkQuery, page }))
        .then(({ page, recovered }) => {
          if (!active) return;
          if (recovered) return;
          setAuthors({ page, loading: false });
        })
        .catch((error: unknown) => { if (active) setAuthors((current) => ({ page: current.page, loading: false, error: normalizeMutationError(error) })); });
    } else {
      setSeries((current) => ({ page: current.page, loading: true }));
      const sdkQuery = libraryAxisSdkQuery(queryState);
      recoverPage((page) => listSeries({ ...sdkQuery, page }))
        .then(({ page, recovered }) => {
          if (!active) return;
          if (recovered) return;
          setSeries({ page, loading: false });
        })
        .catch((error: unknown) => { if (active) setSeries((current) => ({ page: current.page, loading: false, error: normalizeMutationError(error) })); });
    }

    return () => { active = false; };
  }, [listRetry, canonicalQuery, location.state, queryKey, queryState.authorId, queryState.ordering, queryState.page, queryState.pageSize, queryState.q, queryState.seriesId, queryState.tag, requestView, selectedContextDisplay, setSearchParameters]);

  function changeQuery(changes: Parameters<typeof withLibraryChange>[1], resetPage = true) {
    setSearchParameters(librarySearchParams(withLibraryChange(queryState, changes, resetPage)), { state: selectedContextDisplay ? location.state : null });
  }

  const currentLibraryPath = libraryPath(queryState);
  const canEditCatalog = isAtLeastLibrarian(currentUser);
  const selectedContextName = contextDetails.status === "ready" ? contextDetails.details.name : selectedContextDisplay?.name;
  const owningAxisState = selectedContextKind ? withLibrarySelectedContext(queryState, undefined) : queryState;
  const owningAxisPath = libraryPath(owningAxisState);
  const commonListProps = {
    pageNumber: queryState.page,
    pageSize: queryState.pageSize,
    libraryPath: currentLibraryPath,
    onPageChange: (page: number) => changeQuery({ page }, false),
    onPageSizeChange: (pageSize: number) => changeQuery({ pageSize }),
    onRetry: () => setListRetry((value) => value + 1),
  };
  const catalogLayoutKey = catalogLayoutStabilityKey(requestView, queryState);

  return <ProductPageShell className="library-page">
    <LibraryAxesPageRegion
      activeView={queryState.view}
      canManageCatalog={canEditCatalog}
      onViewChange={(view) => navigate(libraryAxisBasePath(queryState, view), { state: null })}
    />
    <LibraryAxisControlsPageRegion
      view={queryState.view}
      selectedContext={selectedContextKind}
      search={searchDraft}
      ordering={queryState.ordering}
      onSearchChange={setSearchDraft}
      onSearch={() => changeQuery({ q: searchDraft.trim() })}
      onOrderingChange={(ordering) => changeQuery({ ordering })}
    />
    <CatalogBrowserPageRegion
      key={catalogLayoutKey}
      tagRail={<CatalogTagRailPageRegion
        tags={tags.tags}
        activeTag={queryState.tag}
        loading={tags.loading}
        error={tags.error}
        onTagChange={(tag) => changeQuery({ tag })}
        onRetry={() => setTagRetry((value) => value + 1)}
      />}
    >
        {selectedContextKind ? <SelectedLibraryContextPageRegion
          kind={selectedContextKind}
          entityId={queryState.authorId ?? queryState.seriesId}
          name={selectedContextName}
          blurb={contextDetails.status === "ready" ? contextDetails.details.blurb : undefined}
          bookCount={contextDetails.status === "ready" ? contextDetails.details.bookCount : selectedContextDisplay?.bookCount}
          loading={contextDetails.status === "loading"}
          unavailable={contextDetails.status === "unavailable"}
          error={contextDetails.status === "error" ? contextDetails.error : undefined}
          canEdit={canEditCatalog}
          returnTo={currentLibraryPath}
          onRetry={() => setContextRetry((value) => value + 1)}
        /> : null}
        {queryState.view === "books" || selectedContextKind ? <BookListPageRegion
          page={books.page}
          loading={books.loading}
          error={books.error}
          searching={Boolean(queryState.q)}
          tagged={Boolean(queryState.tag)}
          selectedContext={selectedContextKind ? {
            kind: selectedContextKind,
            label: selectedContextName ?? (selectedContextKind === "author" ? "Author Books" : "Series Books"),
          } : undefined}
          parentLibraryPath={selectedContextKind ? owningAxisPath : undefined}
          {...commonListProps}
        /> : null}
        {queryState.view === "authors" && !selectedContextKind ? <AuthorListPageRegion
          page={authors.page}
          loading={authors.loading}
          error={authors.error}
          searching={Boolean(queryState.q)}
          tagged={Boolean(queryState.tag)}
          contextPathFor={(author) => libraryPath(withLibrarySelectedContext(queryState, { kind: "author", id: author.id }))}
          {...commonListProps}
        /> : null}
        {queryState.view === "series" && !selectedContextKind ? <SeriesListPageRegion
          page={series.page}
          loading={series.loading}
          error={series.error}
          searching={Boolean(queryState.q)}
          tagged={Boolean(queryState.tag)}
          contextPathFor={(item) => libraryPath(withLibrarySelectedContext(queryState, { kind: "series", id: item.id }))}
          {...commonListProps}
        /> : null}
    </CatalogBrowserPageRegion>
  </ProductPageShell>;
}

export function unknownCatalogTag(activeTag: string | undefined, tags: readonly CatalogTag[] | undefined): boolean {
  return Boolean(activeTag && tags && !tags.some(({ slug }) => slug === activeTag));
}

export function catalogLayoutStabilityKey(
  requestView: LibraryView,
  state: Pick<LibraryUrlState, "pageSize" | "q" | "tag" | "ordering" | "authorId" | "seriesId">,
): string {
  return JSON.stringify([
    requestView,
    state.pageSize,
    state.q,
    state.tag,
    state.ordering,
    state.authorId,
    state.seriesId,
  ]);
}

export async function loadSelectedLibraryContextDetails(
  kind: "author" | "series",
  id: string,
  requests: {
    author: typeof getAuthor;
    series: typeof getSeries;
  } = { author: getAuthor, series: getSeries },
): Promise<SelectedLibraryContextDetails> {
  if (kind === "author") {
    const author = await requests.author(id);
    return { kind, id: author.id, name: author.name, bookCount: author.bookCount, blurb: author.biography };
  }
  const series = await requests.series(id);
  return { kind, id: series.id, name: series.name, bookCount: series.bookCount, blurb: series.summary };
}

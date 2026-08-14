import {
  listMarginaliaBooks,
  listMarginaliaBookSessions,
  listMarginaliaSessions,
  type MarginaliaBookSessionsPage,
  type MarginaliaBookSummary,
  type MarginaliaSessionListItem,
  type Page,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { loadPageWithRecovery } from "../../app/routing/pageRecovery";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { ProductPageShell } from "../../shared/layout/ProductPageShell";
import { marginaliaListBreadcrumbFallback } from "./marginaliaBreadcrumbs";
import { MarginaliaSectionActions } from "./components/MarginaliaSectionActions";
import { MarginaliaViewSelector } from "./components/MarginaliaViewSelector";
import {
  marginaliaBooksSdkQuery,
  marginaliaBookSessionsSdkQuery,
  marginaliaBrowseStage,
  marginaliaListSdkQuery,
  marginaliaListSearchParams,
  marginaliaListStateFromSearchParams,
  marginaliaPath,
  withMarginaliaBookSessionChange,
  withMarginaliaListChange,
  withMarginaliaSearch,
  withMarginaliaView,
  withSelectedMarginaliaBook,
  type MarginaliaListUrlState,
  type MarginaliaView,
} from "./marginaliaQuery";
import { MarginaliaBooksPageRegion } from "./regions/MarginaliaBooksPageRegion";
import { MarginaliaSessionsPageRegion } from "./regions/MarginaliaSessionsPageRegion";
import "./Marginalia.css";

interface LoadState<Item> {
  page?: Page<Item>;
  loading: boolean;
  error?: Error;
}

interface BookSessionsLoadState {
  page?: MarginaliaBookSessionsPage;
  bookId?: string;
  loading: boolean;
  error?: Error;
}

export function MarginaliaSessionsOrchestrator() {
  usePageBreadcrumbs(marginaliaListBreadcrumbFallback);
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(() => marginaliaListStateFromSearchParams(new URLSearchParams(queryKey)), [queryKey]);
  const stage = marginaliaBrowseStage(queryState);
  const canonicalQuery = marginaliaListSearchParams(queryState).toString();
  const activeSearch = stage === "book-sessions" ? queryState.bookSessionQ : queryState.q;
  const [searchDraft, setSearchDraft] = useState(activeSearch);
  const [retry, setRetry] = useState(0);
  const [sessions, setSessions] = useState<LoadState<MarginaliaSessionListItem>>({ loading: true });
  const [books, setBooks] = useState<LoadState<MarginaliaBookSummary>>({ loading: true });
  const [bookSessions, setBookSessions] = useState<BookSessionsLoadState>({ loading: true });
  const recoveredPageKeys = useRef(new Set<string>());

  useEffect(() => setSearchDraft(activeSearch), [activeSearch, stage]);

  useEffect(() => {
    if (queryKey === canonicalQuery) return;
    setSearchParameters(new URLSearchParams(canonicalQuery), { replace: true, state: null });
  }, [canonicalQuery, queryKey, setSearchParameters]);

  useEffect(() => {
    if (queryKey !== canonicalQuery) return;
    let active = true;

    if (stage === "sessions") {
      setSessions((current) => ({ page: current.page, loading: true }));
      const sdkQuery = marginaliaListSdkQuery(queryState);
      recoverPage({
        requestedPage: queryState.page,
        pageSize: queryState.pageSize,
        recoveryKey: `marginalia:sessions:${canonicalQuery}`,
        fetchPage: (page) => listMarginaliaSessions({ ...sdkQuery, page }),
        recoveredState: (page) => withMarginaliaListChange(queryState, { page }, false),
      }).then(({ page, recovered }) => {
        if (active && !recovered) setSessions({ page, loading: false });
      }).catch((error: unknown) => {
        if (active) setSessions((current) => ({ page: current.page, loading: false, error: normalizeMutationError(error) }));
      });
    } else if (stage === "books") {
      setBooks((current) => ({ page: current.page, loading: true }));
      const sdkQuery = marginaliaBooksSdkQuery(queryState);
      recoverPage({
        requestedPage: queryState.page,
        pageSize: queryState.pageSize,
        recoveryKey: `marginalia:books:${canonicalQuery}`,
        fetchPage: (page) => listMarginaliaBooks({ ...sdkQuery, page }),
        recoveredState: (page) => withMarginaliaListChange(queryState, { page }, false),
      }).then(({ page, recovered }) => {
        if (active && !recovered) setBooks({ page, loading: false });
      }).catch((error: unknown) => {
        if (active) setBooks((current) => ({ page: current.page, loading: false, error: normalizeMutationError(error) }));
      });
    } else {
      const bookId = queryState.bookId ?? "";
      setBookSessions((current) => ({
        page: current.bookId === bookId ? current.page : undefined,
        bookId,
        loading: true,
      }));
      const sdkQuery = marginaliaBookSessionsSdkQuery(queryState);
      recoverPage({
        requestedPage: queryState.bookSessionPage,
        pageSize: queryState.bookSessionPageSize,
        recoveryKey: `marginalia:book-sessions:${bookId}:${canonicalQuery}`,
        fetchPage: (page) => listMarginaliaBookSessions(bookId, { ...sdkQuery, page }),
        recoveredState: (page) => withMarginaliaBookSessionChange(queryState, { bookSessionPage: page }, false),
      }).then(({ page, recovered }) => {
        if (active && !recovered) setBookSessions({ page, bookId, loading: false });
      }).catch((error: unknown) => {
        if (active) setBookSessions((current) => ({ page: current.bookId === bookId ? current.page : undefined, bookId, loading: false, error: normalizeMutationError(error) }));
      });
    }

    return () => { active = false; };

    function recoverPage<TPage extends { count: number }>({ requestedPage, pageSize, recoveryKey, fetchPage, recoveredState }: {
      requestedPage: number;
      pageSize: number;
      recoveryKey: string;
      fetchPage: (page: number) => Promise<TPage>;
      recoveredState: (page: number) => MarginaliaListUrlState;
    }) {
      return loadPageWithRecovery({
        requestedPage,
        pageSize,
        recoveryKey,
        recoveredKeys: recoveredPageKeys.current,
        fetchPage,
        buildRecoveredLocation: (page) => marginaliaListSearchParams(recoveredState(page)).toString(),
        replaceLocation: (location) => {
          if (!active) return false;
          setSearchParameters(new URLSearchParams(location), { replace: true, state: null });
          return true;
        },
      });
    }
  }, [canonicalQuery, queryKey, queryState, retry, setSearchParameters, stage]);

  function setQuery(state: MarginaliaListUrlState, replace = false) {
    setSearchParameters(marginaliaListSearchParams(state), { replace, state: null });
  }

  function changeView(view: MarginaliaView) {
    if (view === queryState.view) {
      if (queryState.bookId) setQuery(withSelectedMarginaliaBook(queryState));
      return;
    }
    setQuery(withMarginaliaView(queryState, view));
  }

  function submitSearch() {
    setQuery(withMarginaliaSearch(queryState, searchDraft.trim()));
  }

  const shellActions = <MarginaliaSectionActions activeSection="sessions" />;
  return <ProductPageShell title="My Marginalia" actions={shellActions}>
    <div className="marginalia-browser">
      <MarginaliaViewSelector activeView={queryState.view} onViewChange={changeView} />
      {stage === "sessions" ? <MarginaliaSessionsPageRegion
        page={sessions.page}
        pageNumber={queryState.page}
        pageSize={queryState.pageSize}
        search={searchDraft}
        status={queryState.status}
        loading={sessions.loading}
        error={sessions.error}
        onSearchChange={setSearchDraft}
        onSearch={submitSearch}
        onStatusChange={(status) => setQuery(withMarginaliaListChange(queryState, { status }))}
        onPageChange={(page) => setQuery(withMarginaliaListChange(queryState, { page }, false))}
        onPageSizeChange={(pageSize) => setQuery(withMarginaliaListChange(queryState, { pageSize }))}
        onRetry={() => setRetry((value) => value + 1)}
      /> : null}
      {stage === "books" ? <MarginaliaBooksPageRegion
        page={books.page}
        pageNumber={queryState.page}
        pageSize={queryState.pageSize}
        search={searchDraft}
        loading={books.loading}
        error={books.error}
        bookPath={(bookId) => marginaliaPath(withSelectedMarginaliaBook(queryState, bookId))}
        onSearchChange={setSearchDraft}
        onSearch={submitSearch}
        onPageChange={(page) => setQuery(withMarginaliaListChange(queryState, { page }, false))}
        onPageSizeChange={(pageSize) => setQuery(withMarginaliaListChange(queryState, { pageSize }))}
        onRetry={() => setRetry((value) => value + 1)}
      /> : null}
      {stage === "book-sessions" ? <MarginaliaSessionsPageRegion
        page={bookSessions.page}
        pageNumber={queryState.bookSessionPage}
        pageSize={queryState.bookSessionPageSize}
        search={searchDraft}
        status={queryState.bookSessionStatus}
        loading={bookSessions.loading}
        error={bookSessions.error}
        bookContext={bookSessions.page?.book}
        onBackToBooks={() => setQuery(withSelectedMarginaliaBook(queryState))}
        onSearchChange={setSearchDraft}
        onSearch={submitSearch}
        onStatusChange={(bookSessionStatus) => setQuery(withMarginaliaBookSessionChange(queryState, { bookSessionStatus }))}
        onPageChange={(bookSessionPage) => setQuery(withMarginaliaBookSessionChange(queryState, { bookSessionPage }, false))}
        onPageSizeChange={(bookSessionPageSize) => setQuery(withMarginaliaBookSessionChange(queryState, { bookSessionPageSize }))}
        onRetry={() => setRetry((value) => value + 1)}
      /> : null}
    </div>
  </ProductPageShell>;
}

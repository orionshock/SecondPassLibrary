import {
  listMarginaliaBooks,
  listMarginaliaBookSessions,
  listMarginaliaSessions,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { usePageBreadcrumbs } from "../../../app/navigation/usePageBreadcrumbs";
import { useUrlCollectionLifecycle } from "../../../app/routing/useUrlCollectionLifecycle";
import { normalizeMutationError } from "../../../shared/feedback/mutationState";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import { marginaliaListBreadcrumbFallback } from "../marginaliaBreadcrumbs";
import { MarginaliaSectionActions } from "../components/MarginaliaSectionActions";
import { MarginaliaViewSelector } from "./MarginaliaViewSelector";
import {
  marginaliaBooksSdkQuery,
  marginaliaBookSessionsPath,
  marginaliaBookSessionsSdkQuery,
  marginaliaBrowseStage,
  marginaliaListSdkQuery,
  marginaliaListSearchParams,
  marginaliaListStateFromSearchParams,
  withMarginaliaBookSessionChange,
  withMarginaliaListChange,
  withMarginaliaSearch,
  withMarginaliaView,
  withSelectedMarginaliaBook,
  type MarginaliaListUrlState,
  type MarginaliaView,
} from "./marginaliaQuery";
import { MarginaliaBooksPageRegion } from "./MarginaliaBooksPageRegion";
import { MarginaliaSessionsPageRegion } from "./MarginaliaSessionsPageRegion";
import "../Marginalia.css";

export function MarginaliaSessionsOrchestrator() {
  usePageBreadcrumbs(marginaliaListBreadcrumbFallback);
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(() => marginaliaListStateFromSearchParams(new URLSearchParams(queryKey)), [queryKey]);
  const stage = marginaliaBrowseStage(queryState);
  const canonicalQuery = marginaliaListSearchParams(queryState).toString();
  const activeSearch = stage === "book-sessions" ? queryState.bookSessionQ : queryState.q;
  const [searchDraft, setSearchDraft] = useState(activeSearch);
  const listQuery = marginaliaListSdkQuery(queryState);
  const booksQuery = marginaliaBooksSdkQuery(queryState);
  const bookId = queryState.bookId ?? "";
  const bookSessionsQuery = marginaliaBookSessionsSdkQuery(queryState);
  const sessions = useUrlCollectionLifecycle({
    scope: "marginalia:sessions",
    canonicalQuery,
    page: queryState.page,
    pageSize: queryState.pageSize,
    loadPage: (page) => listMarginaliaSessions({ ...listQuery, page }),
    queryForPage: (page) => marginaliaListSearchParams(withMarginaliaListChange(queryState, { page }, false)).toString(),
    enabled: stage === "sessions",
  });
  const books = useUrlCollectionLifecycle({
    scope: "marginalia:books",
    canonicalQuery,
    page: queryState.page,
    pageSize: queryState.pageSize,
    loadPage: (page) => listMarginaliaBooks({ ...booksQuery, page }),
    queryForPage: (page) => marginaliaListSearchParams(withMarginaliaListChange(queryState, { page }, false)).toString(),
    enabled: stage === "books",
  });
  const bookSessions = useUrlCollectionLifecycle({
    scope: `marginalia:book-sessions:${bookId}`,
    canonicalQuery,
    page: queryState.bookSessionPage,
    pageSize: queryState.bookSessionPageSize,
    loadPage: (page) => listMarginaliaBookSessions(bookId, { ...bookSessionsQuery, page }),
    queryForPage: (page) => marginaliaListSearchParams(withMarginaliaBookSessionChange(queryState, { bookSessionPage: page }, false)).toString(),
    enabled: stage === "book-sessions",
  });

  useEffect(() => setSearchDraft(activeSearch), [activeSearch, stage]);

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
        error={sessions.error === undefined ? undefined : normalizeMutationError(sessions.error)}
        onSearchChange={setSearchDraft}
        onSearch={submitSearch}
        onStatusChange={(status) => setQuery(withMarginaliaListChange(queryState, { status }))}
        onPageChange={(page) => setQuery(withMarginaliaListChange(queryState, { page }, false))}
        onPageSizeChange={(pageSize) => setQuery(withMarginaliaListChange(queryState, { pageSize }))}
        onRetry={sessions.retry}
      /> : null}
      {stage === "books" ? <MarginaliaBooksPageRegion
        page={books.page}
        pageNumber={queryState.page}
        pageSize={queryState.pageSize}
        search={searchDraft}
        loading={books.loading}
        error={books.error === undefined ? undefined : normalizeMutationError(books.error)}
        bookPath={(bookId) => marginaliaBookSessionsPath(bookId, queryState)}
        onSearchChange={setSearchDraft}
        onSearch={submitSearch}
        onPageChange={(page) => setQuery(withMarginaliaListChange(queryState, { page }, false))}
        onPageSizeChange={(pageSize) => setQuery(withMarginaliaListChange(queryState, { pageSize }))}
        onRetry={books.retry}
      /> : null}
      {stage === "book-sessions" ? <MarginaliaSessionsPageRegion
        page={bookSessions.page}
        pageNumber={queryState.bookSessionPage}
        pageSize={queryState.bookSessionPageSize}
        search={searchDraft}
        status={queryState.bookSessionStatus}
        loading={bookSessions.loading}
        error={bookSessions.error === undefined ? undefined : normalizeMutationError(bookSessions.error)}
        bookContext={bookSessions.page?.book}
        onBackToBooks={() => setQuery(withSelectedMarginaliaBook(queryState))}
        onSearchChange={setSearchDraft}
        onSearch={submitSearch}
        onStatusChange={(bookSessionStatus) => setQuery(withMarginaliaBookSessionChange(queryState, { bookSessionStatus }))}
        onPageChange={(bookSessionPage) => setQuery(withMarginaliaBookSessionChange(queryState, { bookSessionPage }, false))}
        onPageSizeChange={(bookSessionPageSize) => setQuery(withMarginaliaBookSessionChange(queryState, { bookSessionPageSize }))}
        onRetry={bookSessions.retry}
      /> : null}
    </div>
  </ProductPageShell>;
}

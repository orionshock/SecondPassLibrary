import { listReadingSessions, type Page, type ReadingSessionSummary } from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { breadcrumbNavigationState } from "../../app/navigation/breadcrumbs";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { loadPageWithRecovery } from "../../app/routing/pageRecovery";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";
import { readingListSdkQuery, readingListSearchParams, readingListStateFromSearchParams, withReadingListChange } from "./readingQuery";
import { ReadingSessionsPageRegion } from "./regions/ReadingSessionsPageRegion";
import { readingImportBreadcrumbFallback, readingListBreadcrumbFallback } from "./readingBreadcrumbs";
import "./Reading.css";

interface ReadingLoadState {
  page?: Page<ReadingSessionSummary>;
  loading: boolean;
  error?: Error;
}

export function ReadingSessionsOrchestrator() {
  usePageBreadcrumbs(readingListBreadcrumbFallback);
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(() => readingListStateFromSearchParams(new URLSearchParams(queryKey)), [queryKey]);
  const canonicalQuery = readingListSearchParams(queryState).toString();
  const [searchDraft, setSearchDraft] = useState(queryState.q);
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<ReadingLoadState>({ loading: true });
  const recoveredPageKeys = useRef(new Set<string>());

  useEffect(() => setSearchDraft(queryState.q), [queryState.q]);

  useEffect(() => {
    if (queryKey === canonicalQuery) return;
    setSearchParameters(new URLSearchParams(canonicalQuery), { replace: true, state: null });
  }, [canonicalQuery, queryKey, setSearchParameters]);

  useEffect(() => {
    if (queryKey !== canonicalQuery) return;
    let active = true;
    setLoad((current) => ({ page: current.page, loading: true }));
    const sdkQuery = readingListSdkQuery(queryState);
    loadPageWithRecovery({
      requestedPage: queryState.page,
      pageSize: queryState.pageSize,
      recoveryKey: `reading:${canonicalQuery}`,
      recoveredKeys: recoveredPageKeys.current,
      fetchPage: (page) => listReadingSessions({ ...sdkQuery, page }),
      buildRecoveredLocation: (page) => readingListSearchParams(withReadingListChange(queryState, { page }, false)).toString(),
      replaceLocation: (location) => {
        if (!active) return false;
        setSearchParameters(new URLSearchParams(location), { replace: true, state: null });
        return true;
      },
    }).then(({ page, recovered }) => {
      if (!active || recovered) return;
      setLoad({ page, loading: false });
    }).catch((error: unknown) => {
      if (active) setLoad((current) => ({ page: current.page, loading: false, error: normalizeMutationError(error) }));
    });
    return () => { active = false; };
  }, [canonicalQuery, queryKey, queryState.page, queryState.pageSize, queryState.q, queryState.status, retry, setSearchParameters]);

  function changeQuery(changes: Parameters<typeof withReadingListChange>[1], resetPage = true) {
    setSearchParameters(readingListSearchParams(withReadingListChange(queryState, changes, resetPage)), { state: null });
  }

  return <ProductPageShellComponent title="My Marginalia" actions={<Link className="button" to="/reading/import" state={breadcrumbNavigationState(readingImportBreadcrumbFallback)}>Import</Link>}>
    <ReadingSessionsPageRegion page={load.page} pageNumber={queryState.page} pageSize={queryState.pageSize} search={searchDraft} status={queryState.status} loading={load.loading} error={load.error} onSearchChange={setSearchDraft} onSearch={() => changeQuery({ q: searchDraft.trim() })} onStatusChange={(status) => changeQuery({ status })} onPageChange={(page) => changeQuery({ page }, false)} onPageSizeChange={(pageSize) => changeQuery({ pageSize })} onRetry={() => setRetry((value) => value + 1)} />
  </ProductPageShellComponent>;
}

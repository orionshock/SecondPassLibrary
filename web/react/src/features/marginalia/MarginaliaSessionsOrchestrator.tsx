import { listReadingSessions, type Page, type ReadingSessionSummary } from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { loadPageWithRecovery } from "../../app/routing/pageRecovery";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";
import { marginaliaListSdkQuery, marginaliaListSearchParams, marginaliaListStateFromSearchParams, withMarginaliaListChange } from "./marginaliaQuery";
import { MarginaliaSectionActionsComponent } from "./components/MarginaliaSectionActionsComponent";
import { MarginaliaSessionsPageRegion } from "./regions/MarginaliaSessionsPageRegion";
import { marginaliaListBreadcrumbFallback } from "./marginaliaBreadcrumbs";
import "./Marginalia.css";

interface MarginaliaLoadState {
  page?: Page<ReadingSessionSummary>;
  loading: boolean;
  error?: Error;
}

export function MarginaliaSessionsOrchestrator() {
  usePageBreadcrumbs(marginaliaListBreadcrumbFallback);
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(() => marginaliaListStateFromSearchParams(new URLSearchParams(queryKey)), [queryKey]);
  const canonicalQuery = marginaliaListSearchParams(queryState).toString();
  const [searchDraft, setSearchDraft] = useState(queryState.q);
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<MarginaliaLoadState>({ loading: true });
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
    const sdkQuery = marginaliaListSdkQuery(queryState);
    loadPageWithRecovery({
      requestedPage: queryState.page,
      pageSize: queryState.pageSize,
      recoveryKey: `marginalia:${canonicalQuery}`,
      recoveredKeys: recoveredPageKeys.current,
      fetchPage: (page) => listReadingSessions({ ...sdkQuery, page }),
      buildRecoveredLocation: (page) => marginaliaListSearchParams(withMarginaliaListChange(queryState, { page }, false)).toString(),
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

  function changeQuery(changes: Parameters<typeof withMarginaliaListChange>[1], resetPage = true) {
    setSearchParameters(marginaliaListSearchParams(withMarginaliaListChange(queryState, changes, resetPage)), { state: null });
  }

  return <ProductPageShellComponent title="My Marginalia" actions={<MarginaliaSectionActionsComponent activeSection="sessions" />}>
    <MarginaliaSessionsPageRegion page={load.page} pageNumber={queryState.page} pageSize={queryState.pageSize} search={searchDraft} status={queryState.status} loading={load.loading} error={load.error} onSearchChange={setSearchDraft} onSearch={() => changeQuery({ q: searchDraft.trim() })} onStatusChange={(status) => changeQuery({ status })} onPageChange={(page) => changeQuery({ page }, false)} onPageSizeChange={(pageSize) => changeQuery({ pageSize })} onRetry={() => setRetry((value) => value + 1)} />
  </ProductPageShellComponent>;
}

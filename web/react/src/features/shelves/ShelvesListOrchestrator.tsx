import { listShelves, type Page, type ShelfSummary } from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { loadPageWithRecovery } from "../../app/routing/pageRecovery";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";
import { ShelvesListPageRegion } from "./regions/ShelvesListPageRegion";
import { shelvesListBreadcrumbFallback } from "./shelvesBreadcrumbs";
import {
  shelvesListSdkQuery,
  shelvesListSearchParams,
  shelvesListStateFromSearchParams,
  withShelvesListChange,
} from "./shelvesQuery";
import "./Shelves.css";

interface ShelvesLoadState {
  page?: Page<ShelfSummary>;
  loading: boolean;
  error?: Error;
}

export function ShelvesListOrchestrator() {
  usePageBreadcrumbs(shelvesListBreadcrumbFallback);
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(
    () => shelvesListStateFromSearchParams(new URLSearchParams(queryKey)),
    [queryKey],
  );
  const canonicalQuery = shelvesListSearchParams(queryState).toString();
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<ShelvesLoadState>({ loading: true });
  const recoveredPageKeys = useRef(new Set<string>());

  useEffect(() => {
    if (queryKey === canonicalQuery) return;
    setSearchParameters(new URLSearchParams(canonicalQuery), { replace: true, state: null });
  }, [canonicalQuery, queryKey, setSearchParameters]);

  useEffect(() => {
    if (queryKey !== canonicalQuery) return;
    let active = true;
    setLoad((current) => ({ page: current.page, loading: true }));
    const sdkQuery = shelvesListSdkQuery(queryState);
    loadPageWithRecovery({
      requestedPage: queryState.page,
      pageSize: queryState.pageSize,
      recoveryKey: `shelves:${canonicalQuery}`,
      recoveredKeys: recoveredPageKeys.current,
      fetchPage: (page) => listShelves({ ...sdkQuery, page }),
      buildRecoveredLocation: (page) => shelvesListSearchParams(withShelvesListChange(queryState, { page }, false)).toString(),
      replaceLocation: (location) => {
        if (!active) return false;
        setSearchParameters(new URLSearchParams(location), { replace: true, state: null });
        return true;
      },
    })
      .then(({ page, recovered }) => {
        if (!active) return;
        if (recovered) return;
        setLoad({ page, loading: false });
      })
      .catch((error: unknown) => {
        if (active) setLoad((current) => ({ page: current.page, loading: false, error: normalizeMutationError(error) }));
      });
    return () => { active = false; };
  }, [canonicalQuery, queryKey, queryState.ordering, queryState.page, queryState.pageSize, queryState.scope, retry, setSearchParameters]);

  function changeQuery(changes: Parameters<typeof withShelvesListChange>[1], resetPage = true) {
    setSearchParameters(shelvesListSearchParams(withShelvesListChange(queryState, changes, resetPage)), { state: null });
  }

  return <ProductPageShellComponent className="shelves-page">
    <ShelvesListPageRegion
      page={load.page}
      pageNumber={queryState.page}
      pageSize={queryState.pageSize}
      scope={queryState.scope}
      ordering={queryState.ordering}
      loading={load.loading}
      error={load.error}
      onScopeChange={(scope) => changeQuery({ scope })}
      onOrderingChange={(ordering) => changeQuery({ ordering })}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={() => setRetry((value) => value + 1)}
    />
  </ProductPageShellComponent>;
}

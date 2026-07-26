import { listShelves, type Page, type ShelfSummary } from "@second-pass/spl-api";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { ShelvesListPageRegion } from "./regions/ShelvesListPageRegion";
import { shelvesListBreadcrumbFallback } from "./shelvesBreadcrumbs";
import { loadShelfPageWithRecovery } from "./shelvesPageRecovery";
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

  useEffect(() => {
    if (queryKey === canonicalQuery) return;
    setSearchParameters(new URLSearchParams(canonicalQuery), { replace: true, state: null });
  }, [canonicalQuery, queryKey, setSearchParameters]);

  useEffect(() => {
    if (queryKey !== canonicalQuery) return;
    let active = true;
    setLoad((current) => ({ page: current.page, loading: true }));
    loadShelfPageWithRecovery(shelvesListSdkQuery(queryState), listShelves)
      .then(({ page, correctedPage }) => {
        if (!active) return;
        if (correctedPage !== queryState.page) {
          setSearchParameters(shelvesListSearchParams(withShelvesListChange(
            queryState,
            { page: correctedPage },
            false,
          )), { replace: true, state: null });
          return;
        }
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

  return <div className="page-stack shelves-page">
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
  </div>;
}

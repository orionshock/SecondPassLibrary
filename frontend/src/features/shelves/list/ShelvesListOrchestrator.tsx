import { listShelves } from "@second-pass/spl-api";
import { useMemo } from "react";
import { useSearchParams } from "react-router";

import { usePageBreadcrumbs } from "../../../app/navigation/usePageBreadcrumbs";
import { useUrlCollectionLifecycle } from "../../../app/routing/useUrlCollectionLifecycle";
import { normalizeMutationError } from "../../../shared/feedback/mutationState";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import { ShelvesListPageRegion } from "./ShelvesListPageRegion";
import { shelvesListBreadcrumbFallback } from "../shelvesBreadcrumbs";
import {
  shelvesListSdkQuery,
  shelvesListSearchParams,
  shelvesListStateFromSearchParams,
  withShelvesListChange,
} from "../shelvesQuery";
import "../Shelves.css";

export function ShelvesListOrchestrator() {
  usePageBreadcrumbs(shelvesListBreadcrumbFallback);
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(
    () => shelvesListStateFromSearchParams(new URLSearchParams(queryKey)),
    [queryKey],
  );
  const canonicalQuery = shelvesListSearchParams(queryState).toString();
  const sdkQuery = shelvesListSdkQuery(queryState);
  const load = useUrlCollectionLifecycle({
    scope: "shelves",
    canonicalQuery,
    page: queryState.page,
    pageSize: queryState.pageSize,
    loadPage: (page) => listShelves({ ...sdkQuery, page }),
    queryForPage: (page) => shelvesListSearchParams(withShelvesListChange(queryState, { page }, false)).toString(),
  });

  function changeQuery(changes: Parameters<typeof withShelvesListChange>[1], resetPage = true) {
    setSearchParameters(shelvesListSearchParams(withShelvesListChange(queryState, changes, resetPage)), { state: null });
  }

  return <ProductPageShell className="shelves-page">
    <ShelvesListPageRegion
      page={load.page}
      pageNumber={queryState.page}
      pageSize={queryState.pageSize}
      scope={queryState.scope}
      ordering={queryState.ordering}
      loading={load.loading}
      error={load.error === undefined ? undefined : normalizeMutationError(load.error)}
      onScopeChange={(scope) => changeQuery({ scope })}
      onOrderingChange={(ordering) => changeQuery({ ordering })}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={load.retry}
    />
  </ProductPageShell>;
}

import { ApiError, getShelf, listShelfItems, type ShelfSummary } from "@second-pass/spl-api";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useParams, useSearchParams } from "react-router";

import { usePageBreadcrumbs } from "../../../app/navigation/usePageBreadcrumbs";
import { useUrlCollectionLifecycle } from "../../../app/routing/useUrlCollectionLifecycle";
import { ErrorPanel } from "../../../components/UiPrimitives";
import { normalizeMutationError } from "../../../shared/feedback/mutationState";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import { ShelfHeaderPageRegion } from "./ShelfHeaderPageRegion";
import { ShelfItemsPageRegion } from "./ShelfItemsPageRegion";
import { shelfDetailBreadcrumbFallback } from "../shelvesBreadcrumbs";
import { shelfEditPath } from "../../../shared/shelves/shelfNavigation";
import { shelfEditNavigationState } from "../shelfLifecycle";
import { shelfScopeFromSummary, validBreadcrumbStateForShelf } from "../shelfScopes";
import {
  shelfDetailPath,
  shelfDetailSearchParams,
  shelfDetailStateFromSearchParams,
  shelfItemsSdkQuery,
  withShelfDetailChange,
} from "../shelvesQuery";
import "../Shelves.css";

type ShelfLoad =
  | { status: "loading" }
  | { status: "ready"; shelf: ShelfSummary }
  | { status: "unavailable" }
  | { status: "error"; error: Error };

export function ShelfDetailOrchestrator() {
  const { shelfId = "" } = useParams<{ shelfId: string }>();
  const location = useLocation();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(
    () => shelfDetailStateFromSearchParams(new URLSearchParams(queryKey)),
    [queryKey],
  );
  const canonicalQuery = shelfDetailSearchParams(queryState).toString();
  const [detailRetry, setDetailRetry] = useState(0);
  const [detail, setDetail] = useState<ShelfLoad>({ status: "loading" });
  const sdkQuery = shelfItemsSdkQuery(queryState);
  const items = useUrlCollectionLifecycle({
    scope: `shelf:${shelfId}`,
    canonicalQuery,
    page: queryState.page,
    pageSize: queryState.pageSize,
    loadPage: (page) => listShelfItems(shelfId, { ...sdkQuery, page }),
    queryForPage: (page) => shelfDetailSearchParams(withShelfDetailChange(queryState, { page }, false)).toString(),
    locationState: location.state,
  });
  const shelf = detail.status === "ready" ? detail.shelf : undefined;
  const scope = shelf ? shelfScopeFromSummary(shelf) : "personal";
  const breadcrumbs = useMemo(
    () => shelfDetailBreadcrumbFallback(scope, shelf?.name),
    [scope, shelf?.name],
  );
  usePageBreadcrumbs(breadcrumbs, false, {
    locationState: shelf ? validBreadcrumbStateForShelf(location.state, shelf) : location.state,
  });

  useEffect(() => {
    let active = true;
    setDetail({ status: "loading" });
    getShelf(shelfId)
      .then((loadedShelf) => { if (active) setDetail({ status: "ready", shelf: loadedShelf }); })
      .catch((error: unknown) => {
        if (!active) return;
        setDetail(error instanceof ApiError && error.status === 404
          ? { status: "unavailable" }
          : { status: "error", error: normalizeMutationError(error) });
      });
    return () => { active = false; };
  }, [detailRetry, shelfId]);

  function changeQuery(
    changes: Parameters<typeof withShelfDetailChange>[1],
    resetPage = true,
    replace = false,
  ) {
    setSearchParameters(shelfDetailSearchParams(withShelfDetailChange(queryState, changes, resetPage)), {
      replace,
      state: location.state,
    });
  }

  if (detail.status === "unavailable") {
    return <section className="shelf-detail-state"><ErrorPanel>Shelf not found or unavailable.</ErrorPanel></section>;
  }

  const currentPath = shelfDetailPath(shelfId, queryState);
  return <ProductPageShell className="shelves-page shelf-detail-page">
    <ShelfHeaderPageRegion
      shelf={shelf}
      loading={detail.status === "loading"}
      error={detail.status === "error" ? detail.error : undefined}
      editPath={shelf?.canEdit ? shelfEditPath(shelf.id) : undefined}
      editNavigationState={shelf?.canEdit ? shelfEditNavigationState(location.state, shelf) : undefined}
      onRetry={() => setDetailRetry((value) => value + 1)}
    />
    {shelf ? <ShelfItemsPageRegion
      shelfId={shelf.id}
      shelfName={shelf.name}
      scope={scope}
      shelfPath={currentPath}
      page={items.page}
      pageNumber={queryState.page}
      pageSize={queryState.pageSize}
      ordering={queryState.ordering}
      loading={items.loading}
      error={items.error === undefined ? undefined : normalizeMutationError(items.error)}
      onOrderingChange={(ordering) => changeQuery({ ordering })}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={items.retry}
    /> : null}
  </ProductPageShell>;
}

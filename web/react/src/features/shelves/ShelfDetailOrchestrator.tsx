import { ApiError, getShelf, listShelfItems, type Page, type ShelfItem, type ShelfSummary } from "@second-pass/spl-api";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useParams, useSearchParams } from "react-router-dom";

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { ErrorPanel } from "../../components/ui";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { ShelfHeaderPageRegion } from "./regions/ShelfHeaderPageRegion";
import { ShelfItemsPageRegion } from "./regions/ShelfItemsPageRegion";
import { shelfDetailBreadcrumbFallback } from "./shelvesBreadcrumbs";
import { shelfEditNavigationState, shelfEditPath } from "./shelfLifecycle";
import { loadShelfPageWithRecovery } from "./shelvesPageRecovery";
import {
  shelfDetailPath,
  shelfDetailSearchParams,
  shelfDetailStateFromSearchParams,
  shelfItemsSdkQuery,
  withShelfDetailChange,
} from "./shelvesQuery";
import "./Shelves.css";

interface ItemsLoad {
  page?: Page<ShelfItem>;
  loading: boolean;
  error?: Error;
}

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
  const [itemsRetry, setItemsRetry] = useState(0);
  const [detail, setDetail] = useState<ShelfLoad>({ status: "loading" });
  const [items, setItems] = useState<ItemsLoad>({ loading: true });
  const shelf = detail.status === "ready" ? detail.shelf : undefined;
  const breadcrumbs = useMemo(() => shelfDetailBreadcrumbFallback(shelf?.name), [shelf?.name]);
  usePageBreadcrumbs(breadcrumbs);

  useEffect(() => {
    if (queryKey === canonicalQuery) return;
    setSearchParameters(new URLSearchParams(canonicalQuery), { replace: true, state: location.state });
  }, [canonicalQuery, location.state, queryKey, setSearchParameters]);

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

  useEffect(() => {
    if (queryKey !== canonicalQuery) return;
    let active = true;
    setItems((current) => ({ page: current.page, loading: true }));
    loadShelfPageWithRecovery(
      shelfItemsSdkQuery(queryState),
      (query) => listShelfItems(shelfId, query),
    )
      .then(({ page, correctedPage }) => {
        if (!active) return;
        if (correctedPage !== queryState.page) {
          changeQuery({ page: correctedPage }, false, true);
          return;
        }
        setItems({ page, loading: false });
      })
      .catch((error: unknown) => {
        if (active) setItems((current) => ({ page: current.page, loading: false, error: normalizeMutationError(error) }));
      });
    return () => { active = false; };
  }, [canonicalQuery, itemsRetry, queryKey, queryState.ordering, queryState.page, queryState.pageSize, shelfId]);

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
  return <div className="page-stack shelves-page shelf-detail-page">
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
      shelfPath={currentPath}
      page={items.page}
      pageNumber={queryState.page}
      pageSize={queryState.pageSize}
      ordering={queryState.ordering}
      loading={items.loading}
      error={items.error}
      onOrderingChange={(ordering) => changeQuery({ ordering })}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={() => setItemsRetry((value) => value + 1)}
    /> : null}
  </div>;
}

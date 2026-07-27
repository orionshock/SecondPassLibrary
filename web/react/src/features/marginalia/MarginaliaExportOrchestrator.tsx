import { downloadCompleteReadingExport, downloadSelectedReadingExport, listReadingSessions, type Page, type ReadingSessionSummary } from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { loadPageWithRecovery } from "../../app/routing/pageRecovery";
import { saveDownloadedFile } from "../../shared/browser/saveDownloadedFile";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";
import { marginaliaExportBreadcrumbFallback } from "./marginaliaBreadcrumbs";
import { MarginaliaSectionActionsComponent } from "./components/MarginaliaSectionActionsComponent";
import { marginaliaExportSelectedBookCount, marginaliaExportSelectedSessions, withMarginaliaExportPageSelection, withMarginaliaExportSessionSelection, type MarginaliaExportSelectionMap } from "./marginaliaExportSelection";
import { marginaliaListSdkQuery, marginaliaListSearchParams, marginaliaListStateFromSearchParams, withMarginaliaListChange } from "./marginaliaQuery";
import { MarginaliaExportPageRegion } from "./regions/MarginaliaExportPageRegion";
import "./Marginalia.css";

interface MarginaliaExportLoadState {
  page?: Page<ReadingSessionSummary>;
  loading: boolean;
  error?: Error;
}

export function MarginaliaExportOrchestrator() {
  usePageBreadcrumbs(marginaliaExportBreadcrumbFallback);
  const location = useLocation();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const query = useMemo(() => marginaliaListStateFromSearchParams(new URLSearchParams(queryKey)), [queryKey]);
  const canonicalQuery = marginaliaListSearchParams(query).toString();
  const [searchDraft, setSearchDraft] = useState(query.q);
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<MarginaliaExportLoadState>({ loading: true });
  const [selection, setSelection] = useState<MarginaliaExportSelectionMap>(new Map());
  const [completeState, setCompleteState] = useState<MutationState>(idleMutationState);
  const [selectedState, setSelectedState] = useState<MutationState>(idleMutationState);
  const recoveredPageKeys = useRef(new Set<string>());

  useEffect(() => setSearchDraft(query.q), [query.q]);

  useEffect(() => {
    if (queryKey === canonicalQuery) return;
    setSearchParameters(new URLSearchParams(canonicalQuery), { replace: true, state: location.state });
  }, [canonicalQuery, location.state, queryKey, setSearchParameters]);

  useEffect(() => {
    if (queryKey !== canonicalQuery) return;
    let active = true;
    setLoad((current) => ({ page: current.page, loading: true }));
    const sdkQuery = marginaliaListSdkQuery(query);
    loadPageWithRecovery({
      requestedPage: query.page,
      pageSize: query.pageSize,
      recoveryKey: `marginalia-export:${canonicalQuery}`,
      recoveredKeys: recoveredPageKeys.current,
      fetchPage: (page) => listReadingSessions({ ...sdkQuery, page }),
      buildRecoveredLocation: (page) => marginaliaListSearchParams(withMarginaliaListChange(query, { page }, false)).toString(),
      replaceLocation: (nextQuery) => {
        if (!active) return false;
        setSearchParameters(new URLSearchParams(nextQuery), { replace: true, state: location.state });
        return true;
      },
    }).then(({ page, recovered }) => {
      if (!active || recovered) return;
      setLoad({ page, loading: false });
    }).catch((error: unknown) => {
      if (active) setLoad((current) => ({ page: current.page, loading: false, error: normalizeMutationError(error) }));
    });
    return () => { active = false; };
  }, [canonicalQuery, location.state, query.page, query.pageSize, query.q, query.status, queryKey, retry, setSearchParameters]);

  function changeQuery(changes: Parameters<typeof withMarginaliaListChange>[1], resetPage = true) {
    setSearchParameters(marginaliaListSearchParams(withMarginaliaListChange(query, changes, resetPage)), { state: location.state });
  }

  async function exportComplete() {
    setCompleteState({ pending: true });
    try {
      saveDownloadedFile(await downloadCompleteReadingExport());
      setCompleteState({ pending: false, message: "Complete archive downloaded." });
    } catch (error: unknown) {
      setCompleteState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function exportSelected() {
    if (!selection.size) return;
    setSelectedState({ pending: true });
    try {
      saveDownloadedFile(await downloadSelectedReadingExport({ sessions: marginaliaExportSelectedSessions(selection) }));
      setSelectedState({ pending: false, message: "Selected Sessions downloaded." });
    } catch (error: unknown) {
      setSelectedState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  const selectedSessionIds = new Set(selection.keys());
  return <ProductPageShellComponent title="Export Marginalia" actions={<MarginaliaSectionActionsComponent activeSection="export" />}>
    <MarginaliaExportPageRegion
      page={load.page}
      pageNumber={query.page}
      pageSize={query.pageSize}
      search={searchDraft}
      status={query.status}
      loading={load.loading}
      loadError={load.error}
      completeState={completeState}
      selectedState={selectedState}
      selectedSessionIds={selectedSessionIds}
      selectedBookCount={marginaliaExportSelectedBookCount(selection)}
      onSearchChange={setSearchDraft}
      onSearch={() => changeQuery({ q: searchDraft.trim() })}
      onStatusChange={(status) => changeQuery({ status })}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={() => setRetry((value) => value + 1)}
      onCompleteExport={() => void exportComplete()}
      onSessionSelectionChange={(session, selected) => setSelection((current) => withMarginaliaExportSessionSelection(current, session, selected))}
      onSelectPage={() => setSelection((current) => withMarginaliaExportPageSelection(current, load.page?.items ?? [], true))}
      onClearSelection={() => setSelection(new Map())}
      onSelectedExport={() => void exportSelected()}
    />
  </ProductPageShellComponent>;
}

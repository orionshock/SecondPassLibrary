import { downloadCompleteMarginaliaExport, downloadSelectedMarginaliaExport, listMarginaliaExportCandidates, MarginaliaExportTooLargeError, type MarginaliaExportCandidate, type Page } from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useSearchParams } from "react-router";

import { usePageBreadcrumbs } from "../../../app/navigation/usePageBreadcrumbs";
import { loadPageWithRecovery } from "../../../app/routing/pageRecovery";
import { saveDownloadedFile } from "../../../shared/browser/saveDownloadedFile";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../../shared/feedback/mutationState";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import { marginaliaExportBreadcrumbFallback } from "../marginaliaBreadcrumbs";
import { MarginaliaSectionActions } from "../components/MarginaliaSectionActions";
import { marginaliaExportSelectedBookCount, marginaliaExportSelectedSessionIds, withMarginaliaExportPageSelection, withMarginaliaExportSessionSelection, type MarginaliaExportSelectionMap } from "./marginaliaExportSelection";
import { marginaliaExportCandidateQuery, marginaliaExportSearchParams, marginaliaExportStateFromSearchParams, withMarginaliaExportChange } from "./marginaliaExportQuery";
import { MarginaliaExportPageRegion, type MarginaliaExportLimitFailure } from "./MarginaliaExportPageRegion";
import "../Marginalia.css";

interface MarginaliaExportLoadState {
  page?: Page<MarginaliaExportCandidate>;
  loading: boolean;
  error?: Error;
}

export function MarginaliaExportOrchestrator() {
  usePageBreadcrumbs(marginaliaExportBreadcrumbFallback);
  const location = useLocation();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const query = useMemo(() => marginaliaExportStateFromSearchParams(new URLSearchParams(queryKey)), [queryKey]);
  const canonicalQuery = marginaliaExportSearchParams(query).toString();
  const [searchDraft, setSearchDraft] = useState(query.q);
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<MarginaliaExportLoadState>({ loading: true });
  const [selection, setSelection] = useState<MarginaliaExportSelectionMap>(new Map());
  const [includeEmptySessions, setIncludeEmptySessions] = useState(false);
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
    const sdkQuery = marginaliaExportCandidateQuery(query, includeEmptySessions);
    loadPageWithRecovery({
      requestedPage: query.page,
      pageSize: query.pageSize,
      recoveryKey: `marginalia-export:${canonicalQuery}`,
      recoveredKeys: recoveredPageKeys.current,
      fetchPage: (page) => listMarginaliaExportCandidates(
        { ...sdkQuery, page },
        { groupByBook: query.view === "books" },
      ),
      buildRecoveredLocation: (page) => marginaliaExportSearchParams(withMarginaliaExportChange(query, { page }, false)).toString(),
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
  }, [canonicalQuery, includeEmptySessions, location.state, query.page, query.pageSize, query.q, query.status, query.view, queryKey, retry, setSearchParameters]);

  function changeQuery(changes: Parameters<typeof withMarginaliaExportChange>[1], resetPage = true) {
    setSearchParameters(marginaliaExportSearchParams(withMarginaliaExportChange(query, changes, resetPage)), { state: location.state });
  }

  async function exportComplete() {
    setCompleteState({ pending: true });
    try {
      saveDownloadedFile(await downloadCompleteMarginaliaExport({ includeEmptySessions }));
      setCompleteState({ pending: false, message: "Complete archive downloaded." });
    } catch (error: unknown) {
      setCompleteState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function exportSelected() {
    if (!selection.size) return;
    setSelectedState({ pending: true });
    try {
      saveDownloadedFile(await downloadSelectedMarginaliaExport({
        readingSessionIds: marginaliaExportSelectedSessionIds(selection),
        includeEmptySessions,
      }));
      setSelectedState({ pending: false, message: "Selected Reading Sessions downloaded." });
    } catch (error: unknown) {
      setSelectedState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  const selectedSessionIds = new Set(selection.keys());
  const completeLimitFailure = marginaliaExportLimitFailure(completeState.error);
  const selectedLimitFailure = marginaliaExportLimitFailure(selectedState.error);
  return <ProductPageShell title="Export Marginalia" actions={<MarginaliaSectionActions activeSection="export" />}>
    <MarginaliaExportPageRegion
      page={load.page}
      pageNumber={query.page}
      pageSize={query.pageSize}
      search={searchDraft}
      status={query.status}
      view={query.view}
      loading={load.loading}
      loadError={load.error}
      completeState={completeState}
      completeLimitFailure={completeLimitFailure}
      selectedState={selectedState}
      selectedLimitFailure={selectedLimitFailure}
      selectedSessionIds={selectedSessionIds}
      selectedBookCount={marginaliaExportSelectedBookCount(selection)}
      includeEmptySessions={includeEmptySessions}
      onIncludeEmptySessionsChange={(include) => {
        setIncludeEmptySessions(include);
        setSelection(new Map());
        setCompleteState(idleMutationState);
        setSelectedState(idleMutationState);
        changeQuery({ page: 1 }, false);
      }}
      onSearchChange={setSearchDraft}
      onSearch={() => changeQuery({ q: searchDraft.trim() })}
      onStatusChange={(status) => changeQuery({ status })}
      onViewChange={(view) => changeQuery({ view })}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={() => setRetry((value) => value + 1)}
      onCompleteExport={() => void exportComplete()}
      onSessionSelectionChange={(session, selected) => setSelection((current) => withMarginaliaExportSessionSelection(current, session, selected))}
      onSelectPage={() => setSelection((current) => withMarginaliaExportPageSelection(current, load.page?.items ?? [], true))}
      onClearSelection={() => setSelection(new Map())}
      onSelectedExport={() => void exportSelected()}
    />
  </ProductPageShell>;
}

export function marginaliaExportLimitFailure(
  error: Error | undefined,
): MarginaliaExportLimitFailure | undefined {
  if (!(error instanceof MarginaliaExportTooLargeError)) return undefined;
  const limitLabel = error.limitKind.endsWith("_bytes")
    ? `Maximum archive size: ${formatByteLimit(error.maximum)}.`
    : `Maximum: ${error.maximum.toLocaleString("en-US")} ${error.limitKind === "annotations" ? "annotations" : "Reading Sessions"}.`;
  return {
    message: error.message,
    guidance: error.guidance,
    limitLabel,
  };
}

function formatByteLimit(bytes: number): string {
  const mebibyte = 1024 * 1024;
  return bytes % mebibyte === 0
    ? `${bytes / mebibyte} MiB`
    : `${bytes.toLocaleString("en-US")} bytes`;
}

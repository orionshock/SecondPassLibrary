import { downloadCompleteMarginaliaExport, downloadSelectedMarginaliaExport, listMarginaliaExportCandidates, MarginaliaExportTooLargeError } from "@second-pass/spl-api";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useSearchParams } from "react-router";

import { usePageBreadcrumbs } from "../../../app/navigation/usePageBreadcrumbs";
import { useUrlCollectionLifecycle } from "../../../app/routing/useUrlCollectionLifecycle";
import { saveDownloadedFile } from "../../../shared/browser/saveDownloadedFile";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../../shared/feedback/mutationState";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import { marginaliaExportBreadcrumbFallback } from "../marginaliaBreadcrumbs";
import { MarginaliaSectionActions } from "../components/MarginaliaSectionActions";
import { marginaliaExportSelectedBookCount, marginaliaExportSelectedSessionIds, withMarginaliaExportPageSelection, withMarginaliaExportSessionSelection, type MarginaliaExportSelectionMap } from "./marginaliaExportSelection";
import { marginaliaExportCandidateQuery, marginaliaExportSearchParams, marginaliaExportStateFromSearchParams, withMarginaliaExportChange } from "./marginaliaExportQuery";
import { MarginaliaExportPageRegion, type MarginaliaExportLimitFailure } from "./MarginaliaExportPageRegion";
import "../Marginalia.css";

export function MarginaliaExportOrchestrator() {
  usePageBreadcrumbs(marginaliaExportBreadcrumbFallback);
  const location = useLocation();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const query = useMemo(() => marginaliaExportStateFromSearchParams(new URLSearchParams(queryKey)), [queryKey]);
  const canonicalQuery = marginaliaExportSearchParams(query).toString();
  const [searchDraft, setSearchDraft] = useState(query.q);
  const [selection, setSelection] = useState<MarginaliaExportSelectionMap>(new Map());
  const [includeEmptySessions, setIncludeEmptySessions] = useState(false);
  const [completeState, setCompleteState] = useState<MutationState>(idleMutationState);
  const [selectedState, setSelectedState] = useState<MutationState>(idleMutationState);
  const sdkQuery = marginaliaExportCandidateQuery(query, includeEmptySessions);
  const load = useUrlCollectionLifecycle({
    scope: `marginalia-export:${includeEmptySessions}`,
    canonicalQuery,
    page: query.page,
    pageSize: query.pageSize,
    loadPage: (page) => listMarginaliaExportCandidates(
      { ...sdkQuery, page },
      { groupByBook: query.view === "books" },
    ),
    queryForPage: (page) => marginaliaExportSearchParams(withMarginaliaExportChange(query, { page }, false)).toString(),
    locationState: location.state,
  });

  useEffect(() => setSearchDraft(query.q), [query.q]);

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
      loadError={load.error === undefined ? undefined : normalizeMutationError(load.error)}
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
      onRetry={load.retry}
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

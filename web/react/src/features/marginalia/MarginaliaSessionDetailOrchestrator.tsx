import { getReadingProgress, getReadingSession, listReadingAnnotations, type Page, type ReadingAnnotation, type ReadingSessionDetail } from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useParams, useSearchParams } from "react-router-dom";

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { loadPageWithRecovery } from "../../app/routing/pageRecovery";
import { Button, ErrorPanel } from "../../components/ui";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";
import { marginaliaSessionBreadcrumbFallback } from "./marginaliaBreadcrumbs";
import { marginaliaAnnotationsSdkQuery, marginaliaSessionDetailSearchParams, marginaliaSessionDetailStateFromSearchParams, withMarginaliaSessionDetailChange } from "./marginaliaSessionDetailQuery";
import { MarginaliaSessionDetailPageRegion, type MarginaliaAnnotationsLoadState, type MarginaliaProgressLoadState } from "./regions/MarginaliaSessionDetailPageRegion";
import "./Marginalia.css";

type SessionLoadState =
  | { status: "loading" }
  | { status: "ready"; session: ReadingSessionDetail }
  | { status: "error"; error: Error };

export function MarginaliaSessionDetailOrchestrator() {
  const { sessionId = "" } = useParams();
  const location = useLocation();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const query = useMemo(() => marginaliaSessionDetailStateFromSearchParams(new URLSearchParams(queryKey)), [queryKey]);
  const canonicalQuery = marginaliaSessionDetailSearchParams(query).toString();
  const [sessionRetry, setSessionRetry] = useState(0);
  const [progressRetry, setProgressRetry] = useState(0);
  const [annotationsRetry, setAnnotationsRetry] = useState(0);
  const [sessionLoad, setSessionLoad] = useState<SessionLoadState>({ status: "loading" });
  const [progressLoad, setProgressLoad] = useState<MarginaliaProgressLoadState>({ loading: true });
  const [annotationsLoad, setAnnotationsLoad] = useState<MarginaliaAnnotationsLoadState>({ loading: true });
  const recoveredPageKeys = useRef(new Set<string>());
  const breadcrumbFallback = useMemo(() => marginaliaSessionBreadcrumbFallback(sessionLoad.status === "ready" ? sessionLoad.session.name : undefined), [sessionLoad]);
  usePageBreadcrumbs(breadcrumbFallback);

  useEffect(() => {
    if (queryKey === canonicalQuery) return;
    setSearchParameters(new URLSearchParams(canonicalQuery), { replace: true, state: location.state });
  }, [canonicalQuery, location.state, queryKey, setSearchParameters]);

  useEffect(() => {
    let active = true;
    setSessionLoad({ status: "loading" });
    setProgressLoad({ loading: true });
    setAnnotationsLoad({ loading: true });
    getReadingSession(sessionId).then((session) => {
      if (active) setSessionLoad({ status: "ready", session });
    }).catch((error: unknown) => {
      if (active) setSessionLoad({ status: "error", error: normalizeMutationError(error) });
    });
    return () => { active = false; };
  }, [sessionId, sessionRetry]);

  useEffect(() => {
    if (sessionLoad.status !== "ready") return;
    let active = true;
    setProgressLoad((current) => ({ progress: current.progress, loading: true }));
    getReadingProgress(sessionLoad.session.id).then((progress) => {
      if (active) setProgressLoad({ progress, loading: false });
    }).catch((error: unknown) => {
      if (active) setProgressLoad((current) => ({ progress: current.progress, loading: false, error: normalizeMutationError(error) }));
    });
    return () => { active = false; };
  }, [progressRetry, sessionLoad]);

  useEffect(() => {
    if (sessionLoad.status !== "ready" || queryKey !== canonicalQuery) return;
    let active = true;
    setAnnotationsLoad((current) => ({ page: current.page, loading: true }));
    const sdkQuery = marginaliaAnnotationsSdkQuery(sessionLoad.session.id, query);
    loadPageWithRecovery({
      requestedPage: query.page,
      pageSize: query.pageSize,
      recoveryKey: `marginalia-session:${sessionLoad.session.id}:${canonicalQuery}`,
      recoveredKeys: recoveredPageKeys.current,
      fetchPage: (page) => listReadingAnnotations({ ...sdkQuery, page }),
      buildRecoveredLocation: (page) => marginaliaSessionDetailSearchParams(withMarginaliaSessionDetailChange(query, { page }, false)).toString(),
      replaceLocation: (nextQuery) => {
        if (!active) return false;
        setSearchParameters(new URLSearchParams(nextQuery), { replace: true, state: location.state });
        return true;
      },
    }).then(({ page, recovered }) => {
      if (!active || recovered) return;
      setAnnotationsLoad({ page, loading: false });
    }).catch((error: unknown) => {
      if (active) setAnnotationsLoad((current) => ({ page: current.page, loading: false, error: normalizeMutationError(error) }));
    });
    return () => { active = false; };
  }, [annotationsRetry, canonicalQuery, location.state, query, queryKey, sessionLoad, setSearchParameters]);

  function changeQuery(changes: Parameters<typeof withMarginaliaSessionDetailChange>[1], resetPage = true) {
    setSearchParameters(marginaliaSessionDetailSearchParams(withMarginaliaSessionDetailChange(query, changes, resetPage)), { state: location.state });
  }

  const title = sessionLoad.status === "ready" ? sessionLoad.session.name.trim() || "Unnamed session" : "Reading session";
  if (sessionLoad.status === "loading") return <ProductPageShellComponent eyebrow="My Marginalia" title={title}><p aria-live="polite" aria-busy="true">Loading reading session...</p></ProductPageShellComponent>;
  if (sessionLoad.status === "error") return <ProductPageShellComponent eyebrow="My Marginalia" title={title}><ErrorPanel>{sessionLoad.error.message}</ErrorPanel><Button type="button" tone="secondary" onClick={() => setSessionRetry((value) => value + 1)}>Retry</Button></ProductPageShellComponent>;

  return <ProductPageShellComponent eyebrow="My Marginalia" title={title}>
    <MarginaliaSessionDetailPageRegion
      session={sessionLoad.session}
      progress={progressLoad}
      annotations={annotationsLoad}
      annotationCategories={query.categories}
      annotationOrder={query.order}
      pageNumber={query.page}
      pageSize={query.pageSize}
      onAnnotationCategoriesChange={(categories) => changeQuery({ categories })}
      onAnnotationOrderChange={(order) => changeQuery({ order })}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetryProgress={() => setProgressRetry((value) => value + 1)}
      onRetryAnnotations={() => setAnnotationsRetry((value) => value + 1)}
    />
  </ProductPageShellComponent>;
}

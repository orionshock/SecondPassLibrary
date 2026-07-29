import { getReadingProgress, getReadingSession, listReadingAnnotations, updateReadingSession, type Page, type ReadingAnnotation, type ReadingSessionDetail } from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useParams, useSearchParams } from "react-router-dom";

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { loadPageWithRecovery } from "../../app/routing/pageRecovery";
import { Button, ErrorPanel } from "../../components/ui";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { useAutoDismissMutationMessage } from "../../shared/feedback/useAutoDismissMutationMessage";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";
import { marginaliaSessionBreadcrumbFallback } from "./marginaliaBreadcrumbs";
import { MarginaliaSessionNoteEditorComponent } from "./components/MarginaliaSessionNoteEditorComponent";
import { MarginaliaSessionTitleEditorComponent } from "./components/MarginaliaSessionTitleEditorComponent";
import { marginaliaAnnotationsSdkQuery, marginaliaSessionDetailSearchParams, marginaliaSessionDetailStateFromSearchParams, withMarginaliaSessionDetailChange } from "./marginaliaSessionDetailQuery";
import { MarginaliaSessionDetailPageRegion, type MarginaliaAnnotationsLoadState, type MarginaliaProgressLoadState } from "./regions/MarginaliaSessionDetailPageRegion";
import "./Marginalia.css";

type SessionLoadState =
  | { status: "loading" }
  | { status: "ready"; session: ReadingSessionDetail }
  | { status: "error"; error: Error };

export async function renameMarginaliaSession(
  session: ReadingSessionDetail,
  draft: string,
  update: typeof updateReadingSession = updateReadingSession,
): Promise<{ session: ReadingSessionDetail; changed: boolean }> {
  const name = draft.trim();
  if (name === session.name.trim()) return { session, changed: false };
  return {
    session: await update(session.id, { name }),
    changed: true,
  };
}

export async function updateMarginaliaSessionNote(
  session: ReadingSessionDetail,
  draft: string,
  update: typeof updateReadingSession = updateReadingSession,
): Promise<{ session: ReadingSessionDetail; changed: boolean }> {
  const notes = draft.trim();
  if (notes === session.notes.trim()) return { session, changed: false };
  return {
    session: await update(session.id, { notes }),
    changed: true,
  };
}

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
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [renameState, setRenameState] = useState<MutationState>(idleMutationState);
  const [editingNote, setEditingNote] = useState(false);
  const [noteDraft, setNoteDraft] = useState("");
  const [noteState, setNoteState] = useState<MutationState>(idleMutationState);
  const recoveredPageKeys = useRef(new Set<string>());
  const breadcrumbFallback = useMemo(() => marginaliaSessionBreadcrumbFallback(sessionLoad.status === "ready" ? sessionLoad.session.name : undefined), [sessionLoad]);
  usePageBreadcrumbs(breadcrumbFallback);
  useAutoDismissMutationMessage(renameState, setRenameState);
  useAutoDismissMutationMessage(noteState, setNoteState);

  useEffect(() => {
    if (queryKey === canonicalQuery) return;
    setSearchParameters(new URLSearchParams(canonicalQuery), { replace: true, state: location.state });
  }, [canonicalQuery, location.state, queryKey, setSearchParameters]);

  useEffect(() => {
    let active = true;
    setEditingName(false);
    setNameDraft("");
    setRenameState(idleMutationState);
    setEditingNote(false);
    setNoteDraft("");
    setNoteState(idleMutationState);
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

  function startNameEdit() {
    if (sessionLoad.status !== "ready" || !sessionLoad.session.isActive || sessionLoad.session.status !== "active") return;
    setNameDraft(sessionLoad.session.name);
    setRenameState(idleMutationState);
    setEditingName(true);
  }

  function cancelNameEdit() {
    if (renameState.pending) return;
    if (sessionLoad.status === "ready") setNameDraft(sessionLoad.session.name);
    setRenameState(idleMutationState);
    setEditingName(false);
  }

  async function saveName() {
    if (sessionLoad.status !== "ready" || !sessionLoad.session.isActive || sessionLoad.session.status !== "active" || renameState.pending) return;
    setRenameState({ pending: true });
    try {
      const { session, changed } = await renameMarginaliaSession(
        sessionLoad.session,
        nameDraft,
      );
      setSessionLoad((current) => current.status === "ready"
        ? { status: "ready", session: { ...current.session, name: session.name, updatedAt: session.updatedAt } }
        : current);
      setNameDraft(session.name);
      setEditingName(false);
      setRenameState(changed ? { pending: false, message: "Session name saved." } : idleMutationState);
    } catch (error: unknown) {
      setRenameState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  function startNoteEdit() {
    if (sessionLoad.status !== "ready" || !sessionLoad.session.isActive || sessionLoad.session.status !== "active") return;
    setNoteDraft(sessionLoad.session.notes);
    setNoteState(idleMutationState);
    setEditingNote(true);
  }

  function cancelNoteEdit() {
    if (noteState.pending) return;
    if (sessionLoad.status === "ready") setNoteDraft(sessionLoad.session.notes);
    setNoteState(idleMutationState);
    setEditingNote(false);
  }

  async function saveNote() {
    if (sessionLoad.status !== "ready" || !sessionLoad.session.isActive || sessionLoad.session.status !== "active" || noteState.pending) return;
    setNoteState({ pending: true });
    try {
      const { session, changed } = await updateMarginaliaSessionNote(sessionLoad.session, noteDraft);
      setSessionLoad((current) => current.status === "ready"
        ? { status: "ready", session: { ...current.session, notes: session.notes, updatedAt: session.updatedAt } }
        : current);
      setNoteDraft(session.notes);
      setEditingNote(false);
      setNoteState(changed ? { pending: false, message: "Session note saved." } : idleMutationState);
    } catch (error: unknown) {
      setNoteState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  const title = sessionLoad.status === "ready" ? sessionLoad.session.name.trim() || "Unnamed session" : "Reading session";
  if (sessionLoad.status === "loading") return <ProductPageShellComponent title={title}><p aria-live="polite" aria-busy="true">Loading reading session...</p></ProductPageShellComponent>;
  if (sessionLoad.status === "error") return <ProductPageShellComponent title={title}><ErrorPanel>{sessionLoad.error.message}</ErrorPanel><Button type="button" tone="secondary" onClick={() => setSessionRetry((value) => value + 1)}>Retry</Button></ProductPageShellComponent>;

  const renameFeedback = renameState.error
    ? <span className="field-error" role="alert">{renameState.error.message}</span>
    : renameState.message
      ? <span className="success-message" role="status">{renameState.message}</span>
      : undefined;
  const noteFeedback = noteState.error
    ? <span className="field-error" role="alert">{noteState.error.message}</span>
    : noteState.message
      ? <span className="success-message" role="status">{noteState.message}</span>
      : undefined;
  const titleEditor = <MarginaliaSessionTitleEditorComponent
    displayName={title}
    editable={sessionLoad.session.isActive && sessionLoad.session.status === "active"}
    draft={nameDraft}
    editing={editingName}
    pending={renameState.pending}
    feedback={renameFeedback}
    onDraftChange={setNameDraft}
    onEdit={startNameEdit}
    onSave={() => void saveName()}
    onCancel={cancelNameEdit}
  />;
  const noteEditor = <MarginaliaSessionNoteEditorComponent
    note={sessionLoad.session.notes}
    editable={sessionLoad.session.isActive && sessionLoad.session.status === "active"}
    draft={noteDraft}
    editing={editingNote}
    pending={noteState.pending}
    feedback={noteFeedback}
    onDraftChange={setNoteDraft}
    onEdit={startNoteEdit}
    onSave={() => void saveNote()}
    onCancel={cancelNoteEdit}
  />;

  return <ProductPageShellComponent title={titleEditor}>
    <MarginaliaSessionDetailPageRegion
      session={sessionLoad.session}
      progress={progressLoad}
      annotations={annotationsLoad}
      sessionNote={noteEditor}
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

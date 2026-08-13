import {
  closeMarginaliaSession,
  deleteMarginaliaSession,
  downloadSelectedMarginaliaExport,
  getMarginaliaSession,
  listMarginaliaSessionAnnotations,
  updateMarginaliaSession,
  type MarginaliaSessionEnvelope,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { Button, ErrorPanel } from "../../components/ui";
import { saveDownloadedFile, type BrowserDownload } from "../../shared/browser/saveDownloadedFile";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { useAutoDismissMutationMessage } from "../../shared/feedback/useAutoDismissMutationMessage";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";
import { marginaliaSessionDisplayName } from "../../shared/marginaliaSessionDisplayName";
import { marginaliaSessionBreadcrumbFallback } from "./marginaliaBreadcrumbs";
import { MarginaliaSessionNoteEditorComponent } from "./components/MarginaliaSessionNoteEditorComponent";
import { MarginaliaSessionTitleEditorComponent } from "./components/MarginaliaSessionTitleEditorComponent";
import { MarginaliaSessionDetailPageRegion, type MarginaliaAnnotationsLoadState } from "./regions/MarginaliaSessionDetailPageRegion";
import "./Marginalia.css";

type SessionLoadState =
  | { status: "loading" }
  | { status: "ready"; detail: MarginaliaSessionEnvelope }
  | { status: "error"; error: Error };

export async function renameMarginaliaSession(
  detail: MarginaliaSessionEnvelope,
  draft: string,
  update: typeof updateMarginaliaSession = updateMarginaliaSession,
): Promise<{ detail: MarginaliaSessionEnvelope; changed: boolean }> {
  const name = draft.trim();
  if (name === detail.session.name.trim()) return { detail, changed: false };
  return { detail: await update(detail.session.id, { name }), changed: true };
}

export async function updateMarginaliaSessionNote(
  detail: MarginaliaSessionEnvelope,
  draft: string,
  update: typeof updateMarginaliaSession = updateMarginaliaSession,
): Promise<{ detail: MarginaliaSessionEnvelope; changed: boolean }> {
  const notes = draft.trim();
  if (notes === detail.session.notes.trim()) return { detail, changed: false };
  return { detail: await update(detail.session.id, { notes }), changed: true };
}

export function closeMarginaliaSessionFromProductUi(
  detail: MarginaliaSessionEnvelope,
  close: typeof closeMarginaliaSession = closeMarginaliaSession,
): Promise<MarginaliaSessionEnvelope> {
  return close(detail.session.id);
}

export async function deleteMarginaliaSessionFromProductUi(
  sessionId: string,
  navigateToMarginalia: (to: string, options: { replace: boolean }) => void,
  remove: typeof deleteMarginaliaSession = deleteMarginaliaSession,
): Promise<void> {
  await remove(sessionId);
  navigateToMarginalia("/marginalia", { replace: true });
}

export async function exportMarginaliaSessionFromProductUi(
  sessionId: string,
  download: typeof downloadSelectedMarginaliaExport = downloadSelectedMarginaliaExport,
  save: (attachment: BrowserDownload) => void = saveDownloadedFile,
): Promise<void> {
  const attachment = await download({
    readingSessionIds: [sessionId],
    includeEmptySessions: true,
  });
  save(attachment);
}

export function MarginaliaSessionDetailOrchestrator() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const [sessionRetry, setSessionRetry] = useState(0);
  const [annotationsRetry, setAnnotationsRetry] = useState(0);
  const [sessionLoad, setSessionLoad] = useState<SessionLoadState>({ status: "loading" });
  const [annotationsLoad, setAnnotationsLoad] = useState<MarginaliaAnnotationsLoadState>({ loading: true });
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [renameState, setRenameState] = useState<MutationState>(idleMutationState);
  const [editingNote, setEditingNote] = useState(false);
  const [noteDraft, setNoteDraft] = useState("");
  const [noteState, setNoteState] = useState<MutationState>(idleMutationState);
  const [closeState, setCloseState] = useState<MutationState>(idleMutationState);
  const [deleteState, setDeleteState] = useState<MutationState>(idleMutationState);
  const [exportState, setExportState] = useState<MutationState>(idleMutationState);
  const deletePending = useRef(false);
  const exportPending = useRef(false);
  const loadedSessionId = sessionLoad.status === "ready" ? sessionLoad.detail.session.id : undefined;
  const breadcrumbFallback = useMemo(
    () => marginaliaSessionBreadcrumbFallback(sessionLoad.status === "ready" ? sessionLoad.detail.session : undefined),
    [sessionLoad],
  );
  usePageBreadcrumbs(breadcrumbFallback);
  useAutoDismissMutationMessage(renameState, setRenameState);
  useAutoDismissMutationMessage(noteState, setNoteState);
  useAutoDismissMutationMessage(closeState, setCloseState);

  useEffect(() => {
    let active = true;
    setEditingName(false);
    setNameDraft("");
    setRenameState(idleMutationState);
    setEditingNote(false);
    setNoteDraft("");
    setNoteState(idleMutationState);
    setCloseState(idleMutationState);
    setDeleteState(idleMutationState);
    setExportState(idleMutationState);
    deletePending.current = false;
    exportPending.current = false;
    setSessionLoad({ status: "loading" });
    setAnnotationsLoad({ loading: true });
    getMarginaliaSession(sessionId).then((detail) => {
      if (active) setSessionLoad({ status: "ready", detail });
    }).catch((error: unknown) => {
      if (active) setSessionLoad({ status: "error", error: normalizeMutationError(error) });
    });
    return () => { active = false; };
  }, [sessionId, sessionRetry]);

  useEffect(() => {
    if (!loadedSessionId) return;
    let active = true;
    setAnnotationsLoad((current) => ({ items: current.items, loading: true }));
    listMarginaliaSessionAnnotations(loadedSessionId).then((items) => {
      if (active) setAnnotationsLoad({ items, loading: false });
    }).catch((error: unknown) => {
      if (active) setAnnotationsLoad((current) => ({ items: current.items, loading: false, error: normalizeMutationError(error) }));
    });
    return () => { active = false; };
  }, [annotationsRetry, loadedSessionId]);

  function startNameEdit() {
    if (sessionLoad.status !== "ready" || sessionLoad.detail.session.status !== "active") return;
    setNameDraft(sessionLoad.detail.session.name);
    setRenameState(idleMutationState);
    setEditingName(true);
  }

  function cancelNameEdit() {
    if (renameState.pending) return;
    if (sessionLoad.status === "ready") setNameDraft(sessionLoad.detail.session.name);
    setRenameState(idleMutationState);
    setEditingName(false);
  }

  async function saveName() {
    if (sessionLoad.status !== "ready" || sessionLoad.detail.session.status !== "active" || renameState.pending) return;
    setRenameState({ pending: true });
    try {
      const { detail, changed } = await renameMarginaliaSession(sessionLoad.detail, nameDraft);
      setSessionLoad({ status: "ready", detail });
      setNameDraft(detail.session.name);
      setEditingName(false);
      setRenameState(changed ? { pending: false, message: "Session name saved." } : idleMutationState);
    } catch (error: unknown) {
      setRenameState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  function startNoteEdit() {
    if (sessionLoad.status !== "ready" || sessionLoad.detail.session.status !== "active") return;
    setNoteDraft(sessionLoad.detail.session.notes);
    setNoteState(idleMutationState);
    setEditingNote(true);
  }

  function cancelNoteEdit() {
    if (noteState.pending) return;
    if (sessionLoad.status === "ready") setNoteDraft(sessionLoad.detail.session.notes);
    setNoteState(idleMutationState);
    setEditingNote(false);
  }

  async function saveNote() {
    if (sessionLoad.status !== "ready" || sessionLoad.detail.session.status !== "active" || noteState.pending) return;
    setNoteState({ pending: true });
    try {
      const { detail, changed } = await updateMarginaliaSessionNote(sessionLoad.detail, noteDraft);
      setSessionLoad({ status: "ready", detail });
      setNoteDraft(detail.session.notes);
      setEditingNote(false);
      setNoteState(changed ? { pending: false, message: "Session note saved." } : idleMutationState);
    } catch (error: unknown) {
      setNoteState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function closeSession() {
    if (sessionLoad.status !== "ready" || sessionLoad.detail.session.status !== "active" || closeState.pending || deletePending.current) return;
    setCloseState({ pending: true });
    try {
      const detail = await closeMarginaliaSessionFromProductUi(sessionLoad.detail);
      setSessionLoad({ status: "ready", detail });
      setEditingName(false);
      setEditingNote(false);
      setCloseState({ pending: false, message: "Session closed." });
    } catch (error: unknown) {
      setCloseState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function deleteSession() {
    if (sessionLoad.status !== "ready" || closeState.pending || deletePending.current || exportPending.current) return;
    deletePending.current = true;
    setDeleteState({ pending: true });
    try {
      await deleteMarginaliaSessionFromProductUi(
        sessionLoad.detail.session.id,
        navigate,
        deleteMarginaliaSession,
      );
    } catch (error: unknown) {
      deletePending.current = false;
      setDeleteState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function exportSession() {
    if (sessionLoad.status !== "ready" || deletePending.current || exportPending.current) return;
    exportPending.current = true;
    setExportState({ pending: true });
    try {
      await exportMarginaliaSessionFromProductUi(sessionLoad.detail.session.id);
      exportPending.current = false;
      setExportState(idleMutationState);
    } catch (error: unknown) {
      exportPending.current = false;
      setExportState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  const title = sessionLoad.status === "ready" ? marginaliaSessionDisplayName(sessionLoad.detail.session) : "Reading session";
  if (sessionLoad.status === "loading") return <ProductPageShellComponent title={title}><p aria-live="polite" aria-busy="true">Loading reading session...</p></ProductPageShellComponent>;
  if (sessionLoad.status === "error") return <ProductPageShellComponent title={title}><ErrorPanel>{sessionLoad.error.message}</ErrorPanel><Button type="button" tone="secondary" onClick={() => setSessionRetry((value) => value + 1)}>Retry</Button></ProductPageShellComponent>;

  const renameFeedback = mutationFeedback(renameState);
  const noteFeedback = mutationFeedback(noteState);
  const editable = sessionLoad.detail.session.status === "active" && !closeState.pending;
  const titleEditor = <MarginaliaSessionTitleEditorComponent
    displayName={title}
    editable={editable}
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
    note={sessionLoad.detail.session.notes}
    editable={editable}
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
      detail={sessionLoad.detail}
      annotations={annotationsLoad}
      sessionNote={noteEditor}
      closeState={closeState}
      deleteState={deleteState}
      exportState={exportState}
      onClose={() => void closeSession()}
      onDelete={() => void deleteSession()}
      onExport={() => void exportSession()}
      onRetryAnnotations={() => setAnnotationsRetry((value) => value + 1)}
    />
  </ProductPageShellComponent>;
}

function mutationFeedback(state: MutationState) {
  if (state.error) return <span className="field-error" role="alert">{state.error.message}</span>;
  if (state.message) return <span className="success-message" role="status">{state.message}</span>;
  return undefined;
}

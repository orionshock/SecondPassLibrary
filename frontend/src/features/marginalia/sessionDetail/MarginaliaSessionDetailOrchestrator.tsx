import {
  closeMarginaliaSession,
  deleteMarginaliaSession,
  downloadSelectedMarginaliaExport,
  getMarginaliaSession,
  listMarginaliaSessionAnnotations,
  updateMarginaliaSession,
  type MarginaliaSessionEnvelope,
} from "@second-pass/spl-api";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";

import { usePageBreadcrumbs } from "../../../app/navigation/usePageBreadcrumbs";
import { Button, ErrorPanel } from "../../../components/UiPrimitives";
import { saveDownloadedFile, type BrowserDownload } from "../../../shared/browser/saveDownloadedFile";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../../shared/feedback/mutationState";
import { useAutoDismissMutationMessage } from "../../../shared/feedback/useAutoDismissMutationMessage";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import { marginaliaSessionDisplayName } from "../../../shared/marginaliaSessionDisplayName";
import "../Marginalia.css";
import { marginaliaSessionBreadcrumbFallback } from "../marginaliaBreadcrumbs";
import { MarginaliaSessionDetailPageRegion, type MarginaliaAnnotationsLoadState } from "./MarginaliaSessionDetailPageRegion";
import { MarginaliaSessionDetailMutationLifecycle } from "./MarginaliaSessionDetailMutationLifecycle";
import { MarginaliaSessionNoteEditor } from "./MarginaliaSessionNoteEditor";
import { MarginaliaSessionTitleEditor } from "./MarginaliaSessionTitleEditor";

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
  const mutationLifecycleRef = useRef<MarginaliaSessionDetailMutationLifecycle | null>(null);
  if (mutationLifecycleRef.current === null) {
    mutationLifecycleRef.current = new MarginaliaSessionDetailMutationLifecycle();
  }
  const mutationLifecycle = mutationLifecycleRef.current;
  const loadedSessionId = sessionLoad.status === "ready" ? sessionLoad.detail.session.id : undefined;
  const breadcrumbFallback = useMemo(
    () => marginaliaSessionBreadcrumbFallback(sessionLoad.status === "ready" ? sessionLoad.detail.session : undefined),
    [sessionLoad],
  );
  usePageBreadcrumbs(breadcrumbFallback);
  useAutoDismissMutationMessage(renameState, setRenameState);
  useAutoDismissMutationMessage(noteState, setNoteState);
  useAutoDismissMutationMessage(closeState, setCloseState);

  useLayoutEffect(() => {
    mutationLifecycle.activate(sessionId);
    return () => mutationLifecycle.invalidate(sessionId);
  }, [mutationLifecycle, sessionId, sessionRetry]);

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
    const token = mutationLifecycle.begin(sessionLoad.detail.session.id, "name");
    if (!token) return;
    setRenameState({ pending: true });
    try {
      const { detail, changed } = await renameMarginaliaSession(sessionLoad.detail, nameDraft);
      const settlement = mutationLifecycle.settle(token);
      if (settlement === "expired") return;
      if (settlement === "discard") {
        setRenameState(idleMutationState);
        return;
      }
      if (changed) publishMetadataField("name", detail);
      setNameDraft(detail.session.name);
      setEditingName(false);
      setRenameState(changed ? { pending: false, message: "Reading Session name saved." } : idleMutationState);
    } catch (error: unknown) {
      const settlement = mutationLifecycle.settle(token);
      if (settlement === "expired") return;
      if (settlement === "discard") {
        setRenameState(idleMutationState);
        return;
      }
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
    const token = mutationLifecycle.begin(sessionLoad.detail.session.id, "note");
    if (!token) return;
    setNoteState({ pending: true });
    try {
      const { detail, changed } = await updateMarginaliaSessionNote(sessionLoad.detail, noteDraft);
      const settlement = mutationLifecycle.settle(token);
      if (settlement === "expired") return;
      if (settlement === "discard") {
        setNoteState(idleMutationState);
        return;
      }
      if (changed) publishMetadataField("notes", detail);
      setNoteDraft(detail.session.notes);
      setEditingNote(false);
      setNoteState(changed ? { pending: false, message: "Reading Session note saved." } : idleMutationState);
    } catch (error: unknown) {
      const settlement = mutationLifecycle.settle(token);
      if (settlement === "expired") return;
      if (settlement === "discard") {
        setNoteState(idleMutationState);
        return;
      }
      setNoteState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function closeSession() {
    if (sessionLoad.status !== "ready" || sessionLoad.detail.session.status !== "active") return;
    const token = mutationLifecycle.begin(sessionLoad.detail.session.id, "close");
    if (!token) return;
    setCloseState({ pending: true });
    try {
      const detail = await closeMarginaliaSessionFromProductUi(sessionLoad.detail);
      if (mutationLifecycle.settle(token) !== "publish") return;
      setSessionLoad({ status: "ready", detail });
      setCloseState({ pending: false, message: "Reading Session closed." });
    } catch (error: unknown) {
      if (mutationLifecycle.settle(token) !== "publish") return;
      setCloseState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function deleteSession() {
    if (sessionLoad.status !== "ready") return;
    const token = mutationLifecycle.begin(sessionLoad.detail.session.id, "delete");
    if (!token) return;
    setDeleteState({ pending: true });
    try {
      await deleteMarginaliaSessionFromProductUi(
        sessionLoad.detail.session.id,
        (to, options) => {
          if (mutationLifecycle.settle(token) === "publish") navigate(to, options);
        },
        deleteMarginaliaSession,
      );
    } catch (error: unknown) {
      if (mutationLifecycle.settle(token) !== "publish") return;
      setDeleteState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function exportSession() {
    if (sessionLoad.status !== "ready") return;
    const token = mutationLifecycle.begin(sessionLoad.detail.session.id, "export");
    if (!token) return;
    setExportState({ pending: true });
    try {
      await exportMarginaliaSessionFromProductUi(sessionLoad.detail.session.id);
      if (mutationLifecycle.settle(token) !== "publish") return;
      setExportState(idleMutationState);
    } catch (error: unknown) {
      if (mutationLifecycle.settle(token) !== "publish") return;
      setExportState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  function publishMetadataField(
    field: "name" | "notes",
    detail: MarginaliaSessionEnvelope,
  ) {
    setSessionLoad((current) => {
      if (current.status !== "ready" || current.detail.session.id !== detail.session.id) return current;
      return {
        status: "ready",
        detail: {
          ...current.detail,
          session: { ...current.detail.session, [field]: detail.session[field] },
        },
      };
    });
  }

  const title = sessionLoad.status === "ready" ? marginaliaSessionDisplayName(sessionLoad.detail.session) : "Reading Session";
  if (sessionLoad.status === "loading") return <ProductPageShell title={title}><p aria-live="polite" aria-busy="true">Loading Reading Session…</p></ProductPageShell>;
  if (sessionLoad.status === "error") return <ProductPageShell title={title}><ErrorPanel>{sessionLoad.error.message}</ErrorPanel><Button type="button" tone="secondary" onClick={() => setSessionRetry((value) => value + 1)}>Retry</Button></ProductPageShell>;

  const renameFeedback = mutationFeedback(renameState);
  const noteFeedback = mutationFeedback(noteState);
  const editable = sessionLoad.detail.session.status === "active" && !closeState.pending && !deleteState.pending;
  const titleEditor = <MarginaliaSessionTitleEditor
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
  const noteEditor = <MarginaliaSessionNoteEditor
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

  return <ProductPageShell title={titleEditor}>
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
  </ProductPageShell>;
}

function mutationFeedback(state: MutationState) {
  if (state.error) return <span className="field-error" role="alert">{state.error.message}</span>;
  if (state.message) return <span className="success-message" role="status">{state.message}</span>;
  return undefined;
}

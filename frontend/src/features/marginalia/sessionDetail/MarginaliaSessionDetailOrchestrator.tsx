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
import { saveDownloadedFile } from "../../../shared/browser/saveDownloadedFile";
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
    mutationLifecycleRef.current = new MarginaliaSessionDetailMutationLifecycle({
      update: updateMarginaliaSession,
      close: closeMarginaliaSession,
      remove: deleteMarginaliaSession,
      download: (id) => downloadSelectedMarginaliaExport({ readingSessionIds: [id], includeEmptySessions: true }),
      save: saveDownloadedFile,
      navigateAfterDelete: () => navigate("/marginalia", { replace: true }),
      publishDetail: (update) => setSessionLoad((current) => current.status === "ready"
        ? { status: "ready", detail: update(current.detail) } : current),
      publishFeedback: (kind, state) => ({
        name: setRenameState, note: setNoteState, close: setCloseState, delete: setDeleteState, export: setExportState,
      })[kind](state),
      finishMetadataEdit: (field, value) => {
        if (field === "name") {
          setNameDraft(value);
          setEditingName(false);
        } else {
          setNoteDraft(value);
          setEditingNote(false);
        }
      },
    });
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
    onSave={() => void mutationLifecycle.saveMetadata(sessionLoad.detail, "name", nameDraft)}
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
    onSave={() => void mutationLifecycle.saveMetadata(sessionLoad.detail, "notes", noteDraft)}
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
      onClose={() => void mutationLifecycle.closeSession(sessionLoad.detail)}
      onDelete={() => void mutationLifecycle.deleteSession(sessionLoad.detail.session.id)}
      onExport={() => void mutationLifecycle.exportSession(sessionLoad.detail.session.id)}
      onRetryAnnotations={() => setAnnotationsRetry((value) => value + 1)}
    />
  </ProductPageShell>;
}

function mutationFeedback(state: MutationState) {
  if (state.error) return <span className="field-error" role="alert">{state.error.message}</span>;
  if (state.message) return <span className="success-message" role="status">{state.message}</span>;
  return undefined;
}

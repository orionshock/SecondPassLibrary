import {
  ApiError,
  createAuthor,
  createSeries,
  deleteAuthor,
  deleteSeries,
  getAuthor,
  getSeries,
  listAuthors,
  listBooks,
  listSeries,
  updateAuthor,
  updateSeries,
  type LibraryAuthor,
  type LibrarySeries,
  type BookPreview,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";

import { breadcrumbNavigationState, resolveBreadcrumbTrail } from "../../../app/navigation/breadcrumbs";
import { usePageBreadcrumbs } from "../../../app/navigation/usePageBreadcrumbs";
import { Button, ErrorPanel } from "../../../components/UiPrimitives";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../../shared/feedback/mutationState";
import { useFormSaveLifecycle } from "../../../shared/forms/useFormSaveLifecycle";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import {
  libraryEntityAxisPath,
  libraryEntityBreadcrumbs,
  libraryEntityEditPath,
  libraryEntityNavigationState,
  libraryEntityParentBreadcrumbs,
  libraryEntitySavedBreadcrumbs,
  readLibraryEntityReturnTo,
  readLibraryEntitySuccessMessage,
  titleKind,
  type LibraryEntityEditMode,
  type LibraryEntityKind,
} from "../authorSeriesLifecycle";
import "./AuthorSeriesEdit.css";
import { AuthorSeriesAttachedBooksPageRegion } from "./AuthorSeriesAttachedBooksPageRegion";
import { AuthorSeriesDangerZonePageRegion } from "./AuthorSeriesDangerZonePageRegion";
import { AuthorSeriesEditFormPageRegion } from "./AuthorSeriesEditFormPageRegion";
import {
  authorEditDraft,
  authorMutationInput,
  authorSeriesEditDraftsEqual,
  emptyAuthorSeriesEditDraft,
  seriesEditDraft,
  seriesMutationInput,
  validateAuthorSeriesEditDraft,
  type AuthorSeriesEditDraft,
} from "./authorSeriesEditDraft";
import { confirmAuthorSeriesDelete, isAttachedBookConflict } from "./authorSeriesDelete";
import {
  DuplicateAdvisoryRequestGate,
  duplicateCandidateEditNavigation,
  duplicateAdvisoryResultLimit,
  duplicateAdvisorySearchTerm,
  scheduleDuplicateAdvisorySearch,
  type DuplicateAdvisoryCandidate,
} from "./authorSeriesDuplicateAdvisory";
import {
  AttachedBooksRequestGate,
  appendAttachedBooks,
  attachedBooksQuery,
} from "./authorSeriesAttachedBooks";

type Entity = LibraryAuthor | LibrarySeries;
type LoadState = { status: "loading" } | { status: "ready"; entity?: Entity } | { status: "not-found" } | { status: "error"; error: Error };
type AttachedBooksState = {
  books: BookPreview[];
  total: number;
  nextPage: number | null;
  pending: boolean;
  error?: Error;
};
type DuplicateAdvisoryState = {
  term?: string;
  candidates: DuplicateAdvisoryCandidate[];
  pending: boolean;
  error?: Error;
};

const emptyAttachedBooksState: AttachedBooksState = {
  books: [],
  total: 0,
  nextPage: 1,
  pending: false,
};

export function AuthorSeriesEditOrchestrator({ kind, mode }: {
  kind: LibraryEntityKind;
  mode: LibraryEntityEditMode;
}) {
  const params = useParams();
  const entityId = kind === "author" ? params.authorId : params.seriesId;
  const location = useLocation();
  const navigate = useNavigate();
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<LoadState>(mode === "new" ? { status: "ready" } : { status: "loading" });
  const lifecycle = useFormSaveLifecycle({
    initialDraft: { ...emptyAuthorSeriesEditDraft },
    draftsEqual: authorSeriesEditDraftsEqual,
    discardMessage: `Discard unsaved ${titleKind(kind)} changes?`,
    initialFeedback: readLibraryEntitySuccessMessage(location.state)
      ? { message: readLibraryEntitySuccessMessage(location.state) }
      : {},
  });
  const { draft, mutation } = lifecycle;
  const [deleteMutation, setDeleteMutation] = useState<MutationState>(idleMutationState);
  const [attachedBooks, setAttachedBooks] = useState<AttachedBooksState>(emptyAttachedBooksState);
  const [duplicateAdvisory, setDuplicateAdvisory] = useState<DuplicateAdvisoryState>({
    candidates: [],
    pending: false,
  });
  const [attachedBooksReload, setAttachedBooksReload] = useState(0);
  const attachedBooksRequests = useRef(new AttachedBooksRequestGate());
  const duplicateAdvisoryRequests = useRef(new DuplicateAdvisoryRequestGate());
  const deletePending = useRef(false);
  const entity = load.status === "ready" ? load.entity : undefined;
  const breadcrumbs = useMemo(
    () => libraryEntityBreadcrumbs(kind, mode, entity?.name, entityId),
    [entity?.name, entityId, kind, mode],
  );
  const resolvedBreadcrumbs = useMemo(
    () => resolveBreadcrumbTrail(location.state, breadcrumbs),
    [breadcrumbs, location.state],
  );
  usePageBreadcrumbs(breadcrumbs);

  useEffect(() => {
    lifecycle.protectNavigation();
    if (mode === "new") {
      const empty = { ...emptyAuthorSeriesEditDraft };
      setLoad({ status: "ready" });
      lifecycle.loadDraft(empty);
      return;
    }
    if (!entityId) {
      setLoad({ status: "not-found" });
      return;
    }
    let active = true;
    setLoad({ status: "loading" });
    const request = kind === "author" ? getAuthor(entityId) : getSeries(entityId);
    request.then((loaded) => {
      if (!active) return;
      const next = kind === "author"
        ? authorEditDraft(loaded as LibraryAuthor)
        : seriesEditDraft(loaded as LibrarySeries);
      setLoad({ status: "ready", entity: loaded });
      lifecycle.loadDraft(next);
    }).catch((error: unknown) => {
      if (!active) return;
      setLoad(error instanceof ApiError && error.status === 404
        ? { status: "not-found" }
        : { status: "error", error: normalizeMutationError(error) });
    });
    return () => { active = false; };
  }, [entityId, kind, mode, retry]);

  useEffect(() => {
    const key = mode === "edit" && entityId ? `${kind}:${entityId}:${attachedBooksReload}` : "";
    attachedBooksRequests.current.reset(key);
    setAttachedBooks(emptyAttachedBooksState);
    if (!key || !entityId) return;
    void loadAttachedBooksPage(1, true, key, kind, entityId);
  }, [attachedBooksReload, entityId, kind, mode]);

  useEffect(() => {
    const term = duplicateAdvisorySearchTerm(draft.name, mode, entity?.name);
    const generation = duplicateAdvisoryRequests.current.next();
    if (!term) {
      setDuplicateAdvisory({ candidates: [], pending: false });
      return () => duplicateAdvisoryRequests.current.invalidate();
    }

    setDuplicateAdvisory({ term, candidates: [], pending: true });
    const cancel = scheduleDuplicateAdvisorySearch(() => {
      const query = {
        q: term,
        excludeId: mode === "edit" ? entityId : undefined,
        ordering: "name" as const,
        page: 1,
        pageSize: duplicateAdvisoryResultLimit,
      };
      const request = kind === "author" ? listAuthors(query) : listSeries(query);
      void request.then((page) => {
        if (!duplicateAdvisoryRequests.current.isCurrent(generation)) return;
        setDuplicateAdvisory({
          term,
          candidates: page.items.filter((candidate) => candidate.id !== entityId),
          pending: false,
        });
      }).catch((error: unknown) => {
        if (!duplicateAdvisoryRequests.current.isCurrent(generation)) return;
        setDuplicateAdvisory({
          term,
          candidates: [],
          pending: false,
          error: normalizeMutationError(error),
        });
      });
    });
    return () => {
      cancel();
      duplicateAdvisoryRequests.current.invalidate();
    };
  }, [draft.name, entity?.name, entityId, kind, mode]);

  async function loadAttachedBooksPage(
    pageNumber: number,
    replace: boolean,
    requestKey = mode === "edit" && entityId ? `${kind}:${entityId}:${attachedBooksReload}` : "",
    requestKind = kind,
    requestEntityId = entityId,
  ) {
    if (!requestEntityId || !attachedBooksRequests.current.start(requestKey)) return;
    setAttachedBooks((current) => ({ ...current, pending: true, error: undefined }));
    try {
      const page = await listBooks(attachedBooksQuery(requestKind, requestEntityId, pageNumber));
      if (!attachedBooksRequests.current.isCurrent(requestKey)) return;
      setAttachedBooks((current) => ({
        books: appendAttachedBooks(replace ? [] : current.books, page.items),
        total: page.count,
        nextPage: page.next ? pageNumber + 1 : null,
        pending: false,
      }));
    } catch (error: unknown) {
      if (!attachedBooksRequests.current.isCurrent(requestKey)) return;
      setAttachedBooks((current) => ({
        ...current,
        pending: false,
        error: normalizeMutationError(error),
      }));
    } finally {
      attachedBooksRequests.current.finish(requestKey);
    }
  }

  function change<K extends keyof AuthorSeriesEditDraft>(field: K, value: AuthorSeriesEditDraft[K]) {
    lifecycle.changeDraft((current) => ({ ...current, [field]: value }));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      validateAuthorSeriesEditDraft(draft);
    } catch (error: unknown) {
      lifecycle.setError(normalizeMutationError(error));
      return;
    }
    if (!lifecycle.beginSave()) return;
    try {
      const saved = await saveEntity(kind, mode, entityId, draft);
      const next = kind === "author"
        ? authorEditDraft(saved as LibraryAuthor)
        : seriesEditDraft(saved as LibrarySeries);
      setLoad({ status: "ready", entity: saved });
      const message = `${titleKind(kind)} saved.`;
      lifecycle.saveSucceeded(next, message);
      const savedBreadcrumbs = libraryEntitySavedBreadcrumbs(
        resolveBreadcrumbTrail(location.state, breadcrumbs),
        kind,
        saved.name,
        saved.id,
      );
      if (mode === "new") {
        lifecycle.permitNavigation();
        const target = libraryEntityEditPath(kind, saved.id);
        navigate(target, {
          replace: true,
          state: libraryEntityNavigationState({
            breadcrumbs: savedBreadcrumbs,
            returnTo: readLibraryEntityReturnTo(location.state) ?? libraryEntityAxisPath(kind),
            successMessage: message,
          }),
        });
      } else {
        navigate(location.pathname, {
          replace: true,
          state: libraryEntityNavigationState({
            breadcrumbs: savedBreadcrumbs,
            returnTo: readLibraryEntityReturnTo(location.state),
          }),
        });
      }
    } catch (error: unknown) {
      lifecycle.saveFailed(normalizeMutationError(error));
    }
  }

  function cancel() {
    if (!lifecycle.confirmDiscard()) return;
    const returnTo = readLibraryEntityReturnTo(location.state) ?? libraryEntityAxisPath(kind);
    const parentBreadcrumbs = libraryEntityParentBreadcrumbs(
      resolveBreadcrumbTrail(location.state, breadcrumbs),
      kind,
      mode,
    );
    navigate(returnTo, { state: breadcrumbNavigationState(parentBreadcrumbs) });
  }

  function selectDuplicateCandidate(candidate: DuplicateAdvisoryCandidate) {
    lifecycle.permitNavigation();
    const target = duplicateCandidateEditNavigation(
      kind,
      candidate,
      readLibraryEntityReturnTo(location.state),
    );
    navigate(target.to, { state: target.state });
  }

  async function removeEntity() {
    if (mode !== "edit" || !entityId || !entity || entity.bookCount > 0 || deletePending.current) return;
    if (!confirmAuthorSeriesDelete(kind, entity.name)) return;
    deletePending.current = true;
    setDeleteMutation({ pending: true });
    try {
      if (kind === "author") await deleteAuthor(entityId);
      else await deleteSeries(entityId);
      lifecycle.permitNavigation();
      navigate(libraryEntityAxisPath(kind), { replace: true, state: null });
    } catch (error: unknown) {
      deletePending.current = false;
      const normalized = normalizeMutationError(error);
      setDeleteMutation({ pending: false, error: normalized });
      if (isAttachedBookConflict(error, kind)) {
        try {
          const refreshed = kind === "author" ? await getAuthor(entityId) : await getSeries(entityId);
          setLoad({ status: "ready", entity: refreshed });
          setAttachedBooksReload((value) => value + 1);
        } catch {
          // Keep the deletion error and last authoritative detail on screen.
        }
      }
    }
  }

  const entityTitle = titleKind(kind);
  if (load.status === "loading") return <div className="author-series-edit-state" aria-busy="true">Loading {entityTitle}...</div>;
  if (load.status === "not-found") return <div className="author-series-edit-state"><ErrorPanel>{entityTitle} not found or unavailable.</ErrorPanel><Link to={libraryEntityAxisPath(kind)}>Back to {entityTitle === "Author" ? "Authors" : "Series"}</Link></div>;
  if (load.status === "error") return <div className="author-series-edit-state"><ErrorPanel>{load.error.message}</ErrorPanel><Button type="button" onClick={() => setRetry((value) => value + 1)}>Retry</Button></div>;

  return <ProductPageShell
    className="author-series-edit-page"
    eyebrow={mode === "new" ? `New ${entityTitle}` : `Editing ${entityTitle}`}
    title={mode === "new" ? `Create ${entityTitle}` : draft.name || entity?.name || entityTitle}
  >
    <AuthorSeriesEditFormPageRegion
      kind={kind}
      draft={draft}
      state={mutation}
      advisory={{
        enabled: Boolean(duplicateAdvisory.term),
        candidates: duplicateAdvisory.candidates,
        pending: duplicateAdvisory.pending,
        error: duplicateAdvisory.error,
        onSelectCandidate: selectDuplicateCandidate,
      }}
      onChange={change}
      onSubmit={(event) => void save(event)}
      onCancel={cancel}
    />
    {mode === "edit" && entity && entityId ? <>
      <AuthorSeriesDangerZonePageRegion
        kind={kind}
        name={entity.name}
        bookCount={entity.bookCount}
        state={deleteMutation}
        controlsDisabled={mutation.pending}
        onDelete={() => void removeEntity()}
      />
      <AuthorSeriesAttachedBooksPageRegion
        kind={kind}
        entityId={entityId}
        bookCount={entity.bookCount}
        books={attachedBooks.books}
        loadedTotal={attachedBooks.total}
        pending={attachedBooks.pending}
        error={attachedBooks.error}
        hasMore={attachedBooks.nextPage !== null}
        onLoadMore={() => {
          if (attachedBooks.nextPage !== null) void loadAttachedBooksPage(attachedBooks.nextPage, false);
        }}
        onRetry={() => {
          if (attachedBooks.nextPage !== null) void loadAttachedBooksPage(attachedBooks.nextPage, attachedBooks.books.length === 0);
        }}
        breadcrumbTrail={resolvedBreadcrumbs}
        editPath={`${location.pathname}${location.search}`}
      />
    </> : null}
  </ProductPageShell>;
}

async function saveEntity(
  kind: LibraryEntityKind,
  mode: LibraryEntityEditMode,
  id: string | undefined,
  draft: AuthorSeriesEditDraft,
): Promise<Entity> {
  if (kind === "author") {
    const input = authorMutationInput(draft);
    return mode === "new" ? createAuthor(input) : updateAuthor(id ?? "", input);
  }
  const input = seriesMutationInput(draft);
  return mode === "new" ? createSeries(input) : updateSeries(id ?? "", input);
}

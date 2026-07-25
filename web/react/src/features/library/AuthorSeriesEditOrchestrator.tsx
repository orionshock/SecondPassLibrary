import {
  ApiError,
  createAuthor,
  createSeries,
  getAuthor,
  getSeries,
  updateAuthor,
  updateSeries,
  type LibraryAuthor,
  type LibrarySeries,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useBlocker, useLocation, useNavigate, useParams } from "react-router-dom";

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { Button, ErrorPanel, PageHeader } from "../../components/ui";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
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
import {
  libraryEntityAxisPath,
  libraryEntityBreadcrumbs,
  libraryEntityEditPath,
  libraryEntityNavigationState,
  readLibraryEntityReturnTo,
  readLibraryEntitySuccessMessage,
  titleKind,
  type LibraryEntityEditMode,
  type LibraryEntityKind,
} from "./authorSeriesLifecycle";
import { AuthorSeriesEditFormPageRegion } from "./regions/AuthorSeriesEditFormPageRegion";
import "./AuthorSeriesEdit.css";

type Entity = LibraryAuthor | LibrarySeries;
type LoadState = { status: "loading" } | { status: "ready"; entity?: Entity } | { status: "not-found" } | { status: "error"; error: Error };

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
  const [draft, setDraft] = useState<AuthorSeriesEditDraft>({ ...emptyAuthorSeriesEditDraft });
  const [baseline, setBaseline] = useState<AuthorSeriesEditDraft>({ ...emptyAuthorSeriesEditDraft });
  const [mutation, setMutation] = useState<MutationState>(() => ({
    ...idleMutationState,
    ...(readLibraryEntitySuccessMessage(location.state) ? { message: readLibraryEntitySuccessMessage(location.state) } : {}),
  }));
  const allowNavigation = useRef(false);
  const entity = load.status === "ready" ? load.entity : undefined;
  const dirty = !authorSeriesEditDraftsEqual(draft, baseline);
  const blocker = useBlocker(({ currentLocation, nextLocation }) => (
    !allowNavigation.current && dirty && currentLocation.pathname !== nextLocation.pathname
  ));
  const breadcrumbs = useMemo(
    () => libraryEntityBreadcrumbs(kind, mode, entity?.name),
    [entity?.name, kind, mode],
  );
  usePageBreadcrumbs(breadcrumbs);

  useEffect(() => {
    const preventUnload = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); };
    window.addEventListener("beforeunload", preventUnload);
    return () => window.removeEventListener("beforeunload", preventUnload);
  }, [dirty]);

  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if (window.confirm(`Discard unsaved ${titleKind(kind)} changes?`)) blocker.proceed();
    else blocker.reset();
  }, [blocker, kind]);

  useEffect(() => {
    allowNavigation.current = false;
    if (mode === "new") {
      const empty = { ...emptyAuthorSeriesEditDraft };
      setLoad({ status: "ready" });
      setDraft(empty);
      setBaseline(empty);
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
      setDraft(next);
      setBaseline(next);
    }).catch((error: unknown) => {
      if (!active) return;
      setLoad(error instanceof ApiError && error.status === 404
        ? { status: "not-found" }
        : { status: "error", error: normalizeMutationError(error) });
    });
    return () => { active = false; };
  }, [entityId, kind, mode, retry]);

  function change<K extends keyof AuthorSeriesEditDraft>(field: K, value: AuthorSeriesEditDraft[K]) {
    setDraft((current) => ({ ...current, [field]: value }));
    setMutation(idleMutationState);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      validateAuthorSeriesEditDraft(draft);
    } catch (error: unknown) {
      setMutation({ pending: false, error: normalizeMutationError(error) });
      return;
    }
    setMutation({ pending: true });
    try {
      const saved = await saveEntity(kind, mode, entityId, draft);
      const next = kind === "author"
        ? authorEditDraft(saved as LibraryAuthor)
        : seriesEditDraft(saved as LibrarySeries);
      setLoad({ status: "ready", entity: saved });
      setDraft(next);
      setBaseline(next);
      const message = `${titleKind(kind)} saved.`;
      if (mode === "new") {
        setMutation({ pending: false, message });
        allowNavigation.current = true;
        const target = libraryEntityEditPath(kind, saved.id);
        navigate(target, {
          replace: true,
          state: libraryEntityNavigationState({
            breadcrumbs: libraryEntityBreadcrumbs(kind, "edit", saved.name),
            returnTo: readLibraryEntityReturnTo(location.state) ?? libraryEntityAxisPath(kind),
            successMessage: message,
          }),
        });
      } else {
        setMutation({ pending: false, message });
        navigate(location.pathname, {
          replace: true,
          state: libraryEntityNavigationState({
            breadcrumbs: libraryEntityBreadcrumbs(kind, "edit", saved.name),
            returnTo: readLibraryEntityReturnTo(location.state),
          }),
        });
      }
    } catch (error: unknown) {
      setMutation({ pending: false, error: normalizeMutationError(error) });
    }
  }

  function cancel() {
    if (dirty && !window.confirm(`Discard unsaved ${titleKind(kind)} changes?`)) return;
    allowNavigation.current = true;
    navigate(readLibraryEntityReturnTo(location.state) ?? libraryEntityAxisPath(kind));
  }

  const entityTitle = titleKind(kind);
  if (load.status === "loading") return <div className="author-series-edit-state" aria-busy="true">Loading {entityTitle}...</div>;
  if (load.status === "not-found") return <div className="author-series-edit-state"><ErrorPanel>{entityTitle} not found or unavailable.</ErrorPanel><Link to={libraryEntityAxisPath(kind)}>Back to {entityTitle === "Author" ? "Authors" : "Series"}</Link></div>;
  if (load.status === "error") return <div className="author-series-edit-state"><ErrorPanel>{load.error.message}</ErrorPanel><Button type="button" onClick={() => setRetry((value) => value + 1)}>Retry</Button></div>;

  return <div className="page-stack author-series-edit-page">
    <PageHeader
      eyebrow={mode === "new" ? `New ${entityTitle}` : `Editing ${entityTitle}`}
      title={mode === "new" ? `Create ${entityTitle}` : draft.name || entity?.name || entityTitle}
    />
    <AuthorSeriesEditFormPageRegion
      kind={kind}
      draft={draft}
      state={mutation}
      onChange={change}
      onSubmit={(event) => void save(event)}
      onCancel={cancel}
    />
  </div>;
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

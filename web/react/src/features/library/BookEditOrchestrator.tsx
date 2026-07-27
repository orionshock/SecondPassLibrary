import {
  ApiError,
  addBookToGroup,
  clearBookCover,
  getBook,
  listAllAuthors,
  listAllCatalogTags,
  listAllLibraryGroups,
  listAllSeries,
  removeBookFromGroup,
  replaceBookCover,
  updateBook,
  type BookDetail,
  type CatalogTag,
  type LibraryAuthor,
  type LibraryGroup,
  type LibrarySeries,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useBlocker, useLocation, useNavigate, useOutletContext, useParams } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { breadcrumbNavigationState, readIncomingBreadcrumbTrail, resolveBreadcrumbTrail } from "../../app/navigation/breadcrumbs";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { BookCoverComponent } from "../../shared/books/BookCoverComponent";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { SaveCancelActionRowComponent } from "../../shared/forms/ActionRowComponent";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";
import { bookDetailBreadcrumbFallback, bookEditBreadcrumbTrail } from "./bookDetailPresentation";
import { bookDetailWithUpdatedCover } from "./bookCoverMutation";
import { bookDetailWithUpdatedGroups, canEditBookGroups } from "./bookGroupMutation";
import {
  bookEditDraftFromBook,
  bookEditDraftsEqual,
  bookEditInputFromDraft,
  validateBookEditDraft,
  type BookEditDraft,
} from "./bookEditDraft";
import { BookDetailStatePageRegion } from "./regions/BookDetailStatePageRegion";
import { BookEditAuthorsSeriesPageRegion } from "./regions/BookEditAuthorsSeriesPageRegion";
import { BookEditBookPageRegion } from "./regions/BookEditBookPageRegion";
import { BookEditCatalogPageRegion } from "./regions/BookEditCatalogPageRegion";
import { BookEditIdentifiersPageRegion } from "./regions/BookEditIdentifiersPageRegion";
import { BookEditGroupsPageRegion } from "./regions/BookEditGroupsPageRegion";
import { BookEditTabsPageRegion, type BookEditTab } from "./regions/BookEditTabsPageRegion";
import { BookCoverEditorComponent } from "./components/BookCoverEditorComponent";
import "./BookEdit.css";

type BookLoad = { status: "loading" } | { status: "ready"; book: BookDetail } | { status: "not-found" } | { status: "error"; error: Error };
type PickerLoad<T> = { loading: boolean; items: T[]; error?: Error };

export function BookEditOrchestrator() {
  const { bookId = "" } = useParams();
  const { currentUser } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const navigate = useNavigate();
  const [bookRetry, setBookRetry] = useState(0);
  const [authorRetry, setAuthorRetry] = useState(0);
  const [seriesRetry, setSeriesRetry] = useState(0);
  const [tagRetry, setTagRetry] = useState(0);
  const [groupRetry, setGroupRetry] = useState(0);
  const [load, setLoad] = useState<BookLoad>({ status: "loading" });
  const [authors, setAuthors] = useState<PickerLoad<LibraryAuthor>>({ loading: true, items: [] });
  const [series, setSeries] = useState<PickerLoad<LibrarySeries>>({ loading: true, items: [] });
  const [tags, setTags] = useState<PickerLoad<CatalogTag>>({ loading: true, items: [] });
  const [groups, setGroups] = useState<PickerLoad<LibraryGroup>>({ loading: false, items: [] });
  const [draft, setDraft] = useState<BookEditDraft>();
  const [baseline, setBaseline] = useState<BookEditDraft>();
  const [tab, setTab] = useState<BookEditTab>("book");
  const [mutation, setMutation] = useState<MutationState>(idleMutationState);
  const [coverMutation, setCoverMutation] = useState<MutationState>(idleMutationState);
  const [coverPendingAction, setCoverPendingAction] = useState<"replace" | "clear">();
  const [selectedCoverFile, setSelectedCoverFile] = useState<File>();
  const [coverInputResetKey, setCoverInputResetKey] = useState(0);
  const [groupMutation, setGroupMutation] = useState<MutationState>(idleMutationState);
  const allowNavigation = useRef(false);
  const book = load.status === "ready" ? load.book : undefined;
  const dirty = Boolean(draft && baseline && !bookEditDraftsEqual(draft, baseline));
  const canEditGroups = canEditBookGroups(currentUser);
  const blocker = useBlocker(({ currentLocation, nextLocation }) => !allowNavigation.current && dirty && currentLocation.pathname !== nextLocation.pathname);
  const fallback = useMemo(() => bookEditBreadcrumbTrail(bookDetailBreadcrumbFallback(book?.title ?? "Book"), bookId, book?.title ?? "Book"), [book?.title, bookId]);
  usePageBreadcrumbs(fallback);

  useEffect(() => {
    const preventUnload = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); };
    window.addEventListener("beforeunload", preventUnload);
    return () => window.removeEventListener("beforeunload", preventUnload);
  }, [dirty]);

  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if (window.confirm("Discard unsaved Book changes?")) blocker.proceed();
    else blocker.reset();
  }, [blocker]);

  useEffect(() => {
    if (!bookId) { setLoad({ status: "not-found" }); return; }
    let active = true;
    setLoad({ status: "loading" });
    setCoverMutation(idleMutationState);
    setCoverPendingAction(undefined);
    setSelectedCoverFile(undefined);
    setCoverInputResetKey((value) => value + 1);
    getBook(bookId).then((value) => {
      if (!active) return;
      const next = bookEditDraftFromBook(value);
      setLoad({ status: "ready", book: value }); setDraft(next); setBaseline(next);
    }).catch((error: unknown) => {
      if (!active) return;
      setLoad(error instanceof ApiError && error.status === 404 ? { status: "not-found" } : { status: "error", error: normalizeMutationError(error) });
    });
    return () => { active = false; };
  }, [bookId, bookRetry]);

  useEffect(() => loadPicker(listAllAuthors, setAuthors), [authorRetry]);
  useEffect(() => loadPicker(listAllSeries, setSeries), [seriesRetry]);
  useEffect(() => loadPicker(listAllCatalogTags, setTags), [tagRetry]);
  useEffect(() => {
    if (!canEditGroups) {
      setGroups({ loading: false, items: [] });
      return;
    }
    return loadPicker(listAllLibraryGroups, setGroups);
  }, [canEditGroups, groupRetry]);
  useEffect(() => {
    if (!canEditGroups && tab === "groups") setTab("book");
  }, [canEditGroups, tab]);

  function change<K extends keyof BookEditDraft>(field: K, value: BookEditDraft[K]) {
    setDraft((current) => current ? { ...current, [field]: value } : current);
    setMutation(idleMutationState);
  }

  function selectCoverFile(file: File | undefined) {
    setSelectedCoverFile(file);
    setCoverMutation(idleMutationState);
  }

  async function replaceCover(file: File) {
    if (!bookId || mutation.pending || coverMutation.pending) return;
    setCoverPendingAction("replace");
    setCoverMutation({ pending: true });
    try {
      const updated = await replaceBookCover(bookId, file);
      setLoad((current) => current.status === "ready" && current.book.id === updated.id
        ? { status: "ready", book: bookDetailWithUpdatedCover(current.book, updated) }
        : current);
      setSelectedCoverFile(undefined);
      setCoverInputResetKey((value) => value + 1);
      setCoverMutation({ pending: false, message: "Cover replaced." });
    } catch (error: unknown) {
      setCoverMutation({ pending: false, error: normalizeMutationError(error) });
    } finally {
      setCoverPendingAction(undefined);
    }
  }

  async function clearCover() {
    if (!bookId || mutation.pending || coverMutation.pending) return;
    setCoverPendingAction("clear");
    setCoverMutation({ pending: true });
    try {
      const updated = await clearBookCover(bookId);
      setLoad((current) => current.status === "ready" && current.book.id === updated.id
        ? { status: "ready", book: bookDetailWithUpdatedCover(current.book, updated) }
        : current);
      setSelectedCoverFile(undefined);
      setCoverInputResetKey((value) => value + 1);
      setCoverMutation({ pending: false, message: "Cover cleared." });
    } catch (error: unknown) {
      setCoverMutation({ pending: false, error: normalizeMutationError(error) });
    } finally {
      setCoverPendingAction(undefined);
    }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft || !bookId || groupMutation.pending) return;
    try {
      validateBookEditDraft(draft);
    } catch (error: unknown) {
      setMutation({ pending: false, error: normalizeMutationError(error) });
      return;
    }
    setMutation({ pending: true });
    try {
      const updated = await updateBook(bookId, bookEditInputFromDraft(draft));
      const next = bookEditDraftFromBook(updated);
      setLoad({ status: "ready", book: updated }); setDraft(next); setBaseline(next);
      setMutation({ pending: false, message: "Book saved." });
      const currentTrail = resolveBreadcrumbTrail(location.state, fallback);
      navigate(location.pathname, { replace: true, state: breadcrumbNavigationState(bookEditBreadcrumbTrail(currentTrail, bookId, updated.title)) });
    } catch (error: unknown) {
      setMutation({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function refreshGroupsAfterMutation(successMessage: string) {
    try {
      const refreshed = await getBook(bookId);
      setLoad((current) => current.status === "ready" && current.book.id === refreshed.id
        ? { status: "ready", book: bookDetailWithUpdatedGroups(current.book, refreshed) }
        : current);
      setGroupMutation({ pending: false, message: successMessage });
    } catch {
      setGroupMutation({
        pending: false,
        error: new Error("The group assignment changed, but current groups could not be refreshed."),
      });
    }
  }

  async function addGroup(groupId: string) {
    if (!bookId || mutation.pending || groupMutation.pending) return;
    setGroupMutation({ pending: true });
    try {
      await addBookToGroup(groupId, bookId);
      await refreshGroupsAfterMutation("Group added.");
    } catch (error: unknown) {
      setGroupMutation({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function removeGroup(group: BookDetail["groups"][number]) {
    if (!bookId || mutation.pending || groupMutation.pending) return;
    const restoresPublic = readyGroupsForRemoval(load, group.id);
    const warning = restoresPublic
      ? `Remove ${group.name}? This will affect group-owned shelves. Public/Common Room will be restored.`
      : `Remove ${group.name}? This will affect group-owned shelves.`;
    if (!window.confirm(warning)) return;
    setGroupMutation({ pending: true });
    try {
      await removeBookFromGroup(group.id, bookId);
      await refreshGroupsAfterMutation("Group removed.");
    } catch (error: unknown) {
      setGroupMutation({ pending: false, error: normalizeMutationError(error) });
    }
  }

  function cancel() {
    if (dirty && !window.confirm("Discard unsaved Book changes?")) return;
    allowNavigation.current = true;
    const incoming = readIncomingBreadcrumbTrail(location.state);
    const detailTrail = incoming?.at(-1)?.label === "Edit" ? incoming.slice(0, -1) : bookDetailBreadcrumbFallback(book?.title ?? "Book");
    navigate(`/library/books/${encodeURIComponent(bookId)}`, { state: breadcrumbNavigationState(detailTrail) });
  }

  if (load.status === "not-found") return <ProductPageShellComponent><BookDetailStatePageRegion state="not-found" /></ProductPageShellComponent>;
  if (load.status === "error") return <ProductPageShellComponent><BookDetailStatePageRegion state="error" error={load.error} onRetry={() => setBookRetry((value) => value + 1)} /></ProductPageShellComponent>;
  if (load.status === "loading" || !draft) return <ProductPageShellComponent><BookDetailStatePageRegion state="loading" /></ProductPageShellComponent>;
  const readyBook = load.book;

  return <ProductPageShellComponent><form className="book-edit-page" onSubmit={save}>
    <aside className="book-edit-cover">
      <BookCoverComponent coverUrl={readyBook.coverUrl} title={readyBook.title} />
      <BookCoverEditorComponent
        coverUrl={readyBook.coverUrl}
        title={readyBook.title}
        selectedFile={selectedCoverFile}
        inputResetKey={coverInputResetKey}
        state={coverMutation}
        pendingAction={coverPendingAction}
        disabled={mutation.pending}
        onFileChange={selectCoverFile}
        onReplace={replaceCover}
        onClear={clearCover}
      />
    </aside>
    <main className="book-edit-content">
      <p className="eyebrow">Editing Book</p>
      <h1>{draft.title || readyBook.title}</h1>
      <p className="book-edit-context">{readyBook.authors.length ? `Authors: ${readyBook.authors.map(({ name }) => name).join(", ")}` : "No assigned Authors"}</p>
      {readyBook.series ? <p className="book-edit-context">Series: {readyBook.series.name}{readyBook.series.seriesIndex ? ` ${readyBook.series.seriesIndex}` : ""}</p> : null}
      <BookEditTabsPageRegion active={tab} showGroups={canEditGroups} onChange={setTab} />
      {tab === "book" ? <BookEditBookPageRegion draft={draft} error={mutation.error} onChange={change} /> : null}
      {tab === "catalog" ? <BookEditCatalogPageRegion draft={draft} error={mutation.error} tags={tags.items} tagsLoading={tags.loading} tagsError={tags.error} onRetryTags={() => setTagRetry((value) => value + 1)} onChange={change} /> : null}
      {tab === "authors-series" ? <BookEditAuthorsSeriesPageRegion draft={draft} error={mutation.error} authors={authors.items} series={series.items} authorsLoading={authors.loading} seriesLoading={series.loading} authorsError={authors.error} seriesError={series.error} returnTo={location.pathname} onRetryAuthors={() => setAuthorRetry((value) => value + 1)} onRetrySeries={() => setSeriesRetry((value) => value + 1)} onChange={change} /> : null}
      {tab === "identifiers" ? <BookEditIdentifiersPageRegion draft={draft} error={mutation.error} onChange={change} /> : null}
      {tab === "groups" && canEditGroups ? <BookEditGroupsPageRegion
        currentGroups={readyBook.groups}
        availableGroups={groups.items}
        loading={groups.loading}
        pickerError={groups.error}
        mutation={groupMutation}
        disabled={mutation.pending || groupMutation.pending}
        onRetry={() => setGroupRetry((value) => value + 1)}
        onSelectionChange={() => setGroupMutation(idleMutationState)}
        onAdd={addGroup}
        onRemove={removeGroup}
      /> : null}
      <SaveCancelActionRowComponent state={mutation} submitLabel="Save Book" pendingLabel="Saving..." disabled={groupMutation.pending} onCancel={cancel} />
    </main>
  </form></ProductPageShellComponent>;
}

function readyGroupsForRemoval(load: BookLoad, removedGroupId: string): boolean {
  if (load.status !== "ready") return false;
  return load.book.groups.length === 1
    && load.book.groups[0]?.id === removedGroupId
    && !load.book.groups[0].isPublicGroup;
}

function loadPicker<T>(request: () => Promise<T[]>, setState: (state: PickerLoad<T>) => void): () => void {
  let active = true;
  setState({ loading: true, items: [] });
  request().then((items) => { if (active) setState({ loading: false, items }); }).catch((error: unknown) => { if (active) setState({ loading: false, items: [], error: normalizeMutationError(error) }); });
  return () => { active = false; };
}

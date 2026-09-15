import {
  ApiError,
  addBookToGroup,
  clearBookCover,
  getBook,
  listAllGroupShelvesForBook,
  removeBookFromGroup,
  removeShelfItem,
  replaceBookCover,
  updateBook,
  type BookDetail,
  type ShelfSummary,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useLocation, useNavigate, useOutletContext, useParams } from "react-router";

import type { AppOutletContext } from "../../../app/layout/AppOrchestrator";
import { breadcrumbNavigationState, readIncomingBreadcrumbTrail, resolveBreadcrumbTrail } from "../../../app/navigation/breadcrumbs";
import { usePageBreadcrumbs } from "../../../app/navigation/usePageBreadcrumbs";
import { BookCover } from "../../../shared/books/BookCover";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../../shared/feedback/mutationState";
import { useAutoDismissMutationMessage } from "../../../shared/feedback/useAutoDismissMutationMessage";
import { SaveCancelActionRow } from "../../../shared/forms/ActionRow";
import { useFormSaveLifecycle } from "../../../shared/forms/useFormSaveLifecycle";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import { tabButtonId, tabPanelId } from "../../../shared/tabs/TabList";
import { bookDetailBreadcrumbFallback, bookEditBreadcrumbTrail, bookEditRelatedBreadcrumbTrail } from "../bookDetailPresentation";
import { bookEditQueryDuringImmediateMutation, bookEditQueryFromSearchParams, bookEditSearchParams, type BookEditTab } from "../bookTabs";
import { BookDetailStatePageRegion } from "../regions/BookDetailStatePageRegion";
import { BookCoverEditor } from "./BookCoverEditor";
import "./BookEdit.css";
import { BookEditAuthorsSeriesPageRegion } from "./BookEditAuthorsSeriesPageRegion";
import { BookEditBookPageRegion } from "./BookEditBookPageRegion";
import { BookEditCatalogPageRegion } from "./BookEditCatalogPageRegion";
import { BookEditGroupsPageRegion } from "./BookEditGroupsPageRegion";
import { BookEditGroupShelvesPageRegion } from "./BookEditGroupShelvesPageRegion";
import { BookEditIdentifiersPageRegion } from "./BookEditIdentifiersPageRegion";
import { BookEditTabsPageRegion } from "./BookEditTabsPageRegion";
import { bookDetailWithUpdatedCover } from "./bookCoverMutation";
import { bookDetailWithUpdatedGroups, canEditBookGroups } from "./bookGroupMutation";
import {
  bookEditDraftFromBook,
  bookEditDraftsEqual,
  bookEditInputFromDraft,
  validateBookEditDraft,
  type BookEditDraft,
} from "./bookEditDraft";
import { useBookEditChoices } from "./useBookEditChoices";

type BookLoad = { status: "loading" } | { status: "ready"; book: BookDetail } | { status: "not-found" } | { status: "error"; error: Error };
type GroupShelvesLoad =
  | { status: "idle" | "loading" }
  | { status: "ready"; shelves: ShelfSummary[] }
  | { status: "error"; error: Error };

export function BookEditOrchestrator() {
  const { bookId = "" } = useParams();
  const { currentUser, serverInfo } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const navigate = useNavigate();
  const [bookRetry, setBookRetry] = useState(0);
  const [groupShelfRetry, setGroupShelfRetry] = useState(0);
  const [load, setLoad] = useState<BookLoad>({ status: "loading" });
  const [groupShelves, setGroupShelves] = useState<GroupShelvesLoad>({ status: "idle" });
  const lifecycle = useFormSaveLifecycle<BookEditDraft | undefined>({
    initialDraft: undefined,
    draftsEqual: (current, baseline) => (
      current === undefined || baseline === undefined
        ? current === baseline
        : bookEditDraftsEqual(current, baseline)
    ),
    discardMessage: "Discard unsaved Book changes?",
  });
  const { draft, mutation } = lifecycle;
  const [coverMutation, setCoverMutation] = useState<MutationState>(idleMutationState);
  const [coverPendingAction, setCoverPendingAction] = useState<"replace" | "clear">();
  const [selectedCoverFile, setSelectedCoverFile] = useState<File>();
  const [coverInputResetKey, setCoverInputResetKey] = useState(0);
  const [groupMutation, setGroupMutation] = useState<MutationState>(idleMutationState);
  const [groupShelfMutation, setGroupShelfMutation] = useState<MutationState>(idleMutationState);
  useAutoDismissMutationMessage(coverMutation, setCoverMutation);
  useAutoDismissMutationMessage(groupMutation, setGroupMutation);
  useAutoDismissMutationMessage(groupShelfMutation, setGroupShelfMutation);
  const book = load.status === "ready" ? load.book : undefined;
  const canEditGroups = canEditBookGroups(currentUser, serverInfo.advancedLibraryGroupsEnabled);
  const immediateMutationPending = groupMutation.pending || groupShelfMutation.pending;
  const requestedEditQuery = useMemo(
    () => bookEditQueryFromSearchParams(new URLSearchParams(location.search), canEditGroups),
    [canEditGroups, location.search],
  );
  const stableEditQuery = useRef(requestedEditQuery);
  if (!immediateMutationPending) stableEditQuery.current = requestedEditQuery;
  const editQuery = bookEditQueryDuringImmediateMutation(
    requestedEditQuery,
    stableEditQuery.current,
    immediateMutationPending,
  );
  const tab = editQuery.tab;
  const choices = useBookEditChoices({
    book,
    tab,
    canEditGroups,
    selectedAuthorIds: draft?.authorIds ?? [],
    selectedSeriesId: draft?.seriesId ?? null,
  });
  const fallback = useMemo(() => bookEditBreadcrumbTrail(bookDetailBreadcrumbFallback(book?.title ?? "Book"), bookId, book?.title ?? "Book"), [book?.title, bookId]);
  const breadcrumbTrail = resolveBreadcrumbTrail(location.state, fallback);
  usePageBreadcrumbs(fallback);

  useEffect(() => {
    const currentQuery = location.search.startsWith("?") ? location.search.slice(1) : location.search;
    if (currentQuery === editQuery.query) return;
    navigate({ pathname: location.pathname, search: editQuery.query }, {
      replace: true,
      state: location.state,
    });
  }, [editQuery.query, location.pathname, location.search, location.state, navigate]);

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
      setLoad({ status: "ready", book: value }); lifecycle.loadDraft(next);
    }).catch((error: unknown) => {
      if (!active) return;
      setLoad(error instanceof ApiError && error.status === 404 ? { status: "not-found" } : { status: "error", error: normalizeMutationError(error) });
    });
    return () => { active = false; };
  }, [bookId, bookRetry]);

  useEffect(() => {
    if (tab !== "group-shelves" || !bookId) return;
    let active = true;
    setGroupShelves({ status: "loading" });
    listAllGroupShelvesForBook(bookId).then((shelves) => {
      if (active) setGroupShelves({ status: "ready", shelves });
    }).catch((error: unknown) => {
      if (active) setGroupShelves({ status: "error", error: normalizeMutationError(error) });
    });
    return () => { active = false; };
  }, [bookId, groupShelfRetry, tab]);
  function change<K extends keyof BookEditDraft>(field: K, value: BookEditDraft[K]) {
    lifecycle.changeDraft((current) => current ? { ...current, [field]: value } : current);
  }

  function selectCoverFile(file: File | undefined) {
    setSelectedCoverFile(file);
    setCoverMutation(idleMutationState);
  }

  async function replaceCover(file: File) {
    if (!bookId || mutation.pending || coverMutation.pending) return false;
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
      return true;
    } catch (error: unknown) {
      setCoverMutation({ pending: false, error: normalizeMutationError(error) });
      return false;
    } finally {
      setCoverPendingAction(undefined);
    }
  }

  async function clearCover() {
    if (!bookId || mutation.pending || coverMutation.pending) return false;
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
      return true;
    } catch (error: unknown) {
      setCoverMutation({ pending: false, error: normalizeMutationError(error) });
      return false;
    } finally {
      setCoverPendingAction(undefined);
    }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft || !bookId || coverMutation.pending || immediateMutationPending) return;
    try {
      validateBookEditDraft(draft);
    } catch (error: unknown) {
      lifecycle.setError(normalizeMutationError(error));
      return;
    }
    if (!lifecycle.beginSave()) return;
    try {
      const updated = await updateBook(bookId, bookEditInputFromDraft(draft));
      const next = bookEditDraftFromBook(updated);
      setLoad({ status: "ready", book: updated }); lifecycle.saveSucceeded(next, "Book saved.");
      const currentTrail = resolveBreadcrumbTrail(location.state, fallback);
      navigate({ pathname: location.pathname, search: location.search }, { replace: true, state: breadcrumbNavigationState(bookEditBreadcrumbTrail(currentTrail, bookId, updated.title)) });
    } catch (error: unknown) {
      lifecycle.saveFailed(normalizeMutationError(error));
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

  async function removeGroupShelf(shelf: ShelfSummary) {
    if (!shelf.canEdit || !shelf.matchedItemId || mutation.pending || immediateMutationPending) return;
    if (!window.confirm("Remove this book from the group shelf?")) return;
    setGroupShelfMutation({ pending: true });
    try {
      await removeShelfItem(shelf.id, shelf.matchedItemId);
      const shelves = await listAllGroupShelvesForBook(bookId);
      setGroupShelves({ status: "ready", shelves });
      setGroupShelfMutation({ pending: false, message: "Book removed from group shelf." });
    } catch (error: unknown) {
      setGroupShelfMutation({ pending: false, error: normalizeMutationError(error) });
    }
  }

  function cancel() {
    if (!lifecycle.confirmDiscard()) return;
    const incoming = readIncomingBreadcrumbTrail(location.state);
    const detailTrail = incoming?.at(-1)?.label === "Edit" ? incoming.slice(0, -1) : bookDetailBreadcrumbFallback(book?.title ?? "Book");
    navigate(`/library/books/${encodeURIComponent(bookId)}`, { state: breadcrumbNavigationState(detailTrail) });
  }

  function changeTab(nextTab: BookEditTab) {
    const parameters = bookEditSearchParams(new URLSearchParams(location.search), nextTab);
    navigate({ pathname: location.pathname, search: parameters.toString() }, {
      state: location.state,
    });
  }

  if (load.status === "not-found") return <ProductPageShell><BookDetailStatePageRegion state="not-found" /></ProductPageShell>;
  if (load.status === "error") return <ProductPageShell><BookDetailStatePageRegion state="error" error={load.error} onRetry={() => setBookRetry((value) => value + 1)} /></ProductPageShell>;
  if (load.status === "loading" || !draft) return <ProductPageShell><BookDetailStatePageRegion state="loading" /></ProductPageShell>;
  const readyBook = load.book;

  return <ProductPageShell><form className="book-edit-page" aria-busy={mutation.pending} onSubmit={save}>
    <aside className="book-edit-cover">
      <BookCover coverUrl={readyBook.coverUrl} title={readyBook.title} />
      <BookCoverEditor
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
    <div className="book-edit-content">
      <p className="eyebrow">Editing Book</p>
      <h1>{draft.title || readyBook.title}</h1>
      <div className="book-edit-summary">
        <p className="book-edit-context">{readyBook.authors.length ? `Authors: ${readyBook.authors.map(({ name }) => name).join(", ")}` : "No assigned Authors"}</p>
        {readyBook.series ? <p className="book-edit-context">Series: {readyBook.series.name}{readyBook.series.seriesIndex ? ` ${readyBook.series.seriesIndex}` : ""}</p> : null}
      </div>
      <BookEditTabsPageRegion active={tab} showGroups={canEditGroups} disabled={mutation.pending || immediateMutationPending} onChange={changeTab} />
      <div id={tabPanelId("book-edit", tab)} role="tabpanel" aria-labelledby={tabButtonId("book-edit", tab)}>
      {tab === "book" ? <BookEditBookPageRegion draft={draft} error={mutation.error} disabled={mutation.pending} onChange={change} /> : null}
      {tab === "catalog" ? <BookEditCatalogPageRegion draft={draft} error={mutation.error} tags={choices.tags.items} tagQuery={choices.tags.query} tagsLoading={choices.tags.loading} tagsError={choices.tags.error} disabled={mutation.pending} onTagQueryChange={choices.tags.setQuery} onRetryTags={choices.tags.retry} onChange={change} /> : null}
      {tab === "authors-series" ? <BookEditAuthorsSeriesPageRegion draft={draft} error={mutation.error} authors={choices.authors.items} series={choices.series.items} authorQuery={choices.authors.query} seriesQuery={choices.series.query} authorsLoading={choices.authors.loading} seriesLoading={choices.series.loading} authorsError={choices.authors.error} seriesError={choices.series.error} breadcrumbTrail={breadcrumbTrail} returnTo={`${location.pathname}${location.search}`} disabled={mutation.pending} onAuthorQueryChange={choices.authors.setQuery} onSeriesQueryChange={choices.series.setQuery} onRetryAuthors={choices.authors.retry} onRetrySeries={choices.series.retry} onChange={change} /> : null}
      {tab === "identifiers" ? <BookEditIdentifiersPageRegion draft={draft} error={mutation.error} disabled={mutation.pending} onChange={change} /> : null}
      {tab === "groups" && canEditGroups ? <BookEditGroupsPageRegion
        currentGroups={readyBook.groups}
        availableGroups={choices.groups.items}
        query={choices.groups.query}
        loading={choices.groups.loading}
        pickerError={choices.groups.error}
        mutation={groupMutation}
        disabled={mutation.pending || immediateMutationPending}
        groupNavigationState={(group) => breadcrumbNavigationState(bookEditRelatedBreadcrumbTrail(
          breadcrumbTrail,
          `${location.pathname}${location.search}`,
          { label: group.name, icon: group.isPublicGroup ? "public-group" : "group" },
        ))}
        onQueryChange={choices.groups.setQuery}
        onRetry={choices.groups.retry}
        onSelectionChange={() => setGroupMutation(idleMutationState)}
        onAdd={addGroup}
        onRemove={removeGroup}
      /> : null}
      {tab === "group-shelves" ? <BookEditGroupShelvesPageRegion
        shelves={groupShelves.status === "ready" ? groupShelves.shelves : []}
        loading={groupShelves.status === "idle" || groupShelves.status === "loading"}
        error={groupShelves.status === "error" ? groupShelves.error : undefined}
        mutation={groupShelfMutation}
        disabled={mutation.pending || immediateMutationPending}
        shelfNavigationState={(shelf) => breadcrumbNavigationState(bookEditRelatedBreadcrumbTrail(
          breadcrumbTrail,
          `${location.pathname}${location.search}`,
          { label: shelf.name, icon: "shelf" },
        ))}
        onRetry={() => { setGroupShelfMutation(idleMutationState); setGroupShelfRetry((value) => value + 1); }}
        onRemove={(shelf) => void removeGroupShelf(shelf)}
      /> : null}
      </div>
      <SaveCancelActionRow state={mutation} submitLabel="Save Book" pendingLabel="Saving..." disabled={coverMutation.pending || immediateMutationPending} onCancel={cancel} />
    </div>
  </form></ProductPageShell>;
}

function readyGroupsForRemoval(load: BookLoad, removedGroupId: string): boolean {
  if (load.status !== "ready") return false;
  return load.book.groups.length === 1
    && load.book.groups[0]?.id === removedGroupId
    && !load.book.groups[0].isPublicGroup;
}

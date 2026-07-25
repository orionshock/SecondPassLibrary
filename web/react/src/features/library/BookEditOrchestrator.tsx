import {
  ApiError,
  clearBookCover,
  getBook,
  listAllAuthors,
  listAllCatalogTags,
  listAllSeries,
  replaceBookCover,
  updateBook,
  type BookDetail,
  type CatalogTag,
  type LibraryAuthor,
  type LibrarySeries,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useBlocker, useLocation, useNavigate, useParams } from "react-router-dom";

import { breadcrumbNavigationState, readIncomingBreadcrumbTrail, resolveBreadcrumbTrail } from "../../app/navigation/breadcrumbs";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { Button, ErrorPanel } from "../../components/ui";
import { BookCoverComponent } from "../../shared/books/BookCoverComponent";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { SaveCancelActionRowComponent } from "../../shared/forms/ActionRowComponent";
import { bookDetailBreadcrumbFallback, bookEditBreadcrumbTrail } from "./bookDetailPresentation";
import { bookDetailWithUpdatedCover } from "./bookCoverMutation";
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
import { BookEditTabsPageRegion, type BookEditTab } from "./regions/BookEditTabsPageRegion";
import { BookCoverEditorComponent } from "./components/BookCoverEditorComponent";
import "./BookEdit.css";

type BookLoad = { status: "loading" } | { status: "ready"; book: BookDetail } | { status: "not-found" } | { status: "error"; error: Error };
type PickerLoad<T> = { loading: boolean; items: T[]; error?: Error };

export function BookEditOrchestrator() {
  const { bookId = "" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [bookRetry, setBookRetry] = useState(0);
  const [authorRetry, setAuthorRetry] = useState(0);
  const [seriesRetry, setSeriesRetry] = useState(0);
  const [tagRetry, setTagRetry] = useState(0);
  const [load, setLoad] = useState<BookLoad>({ status: "loading" });
  const [authors, setAuthors] = useState<PickerLoad<LibraryAuthor>>({ loading: true, items: [] });
  const [series, setSeries] = useState<PickerLoad<LibrarySeries>>({ loading: true, items: [] });
  const [tags, setTags] = useState<PickerLoad<CatalogTag>>({ loading: true, items: [] });
  const [draft, setDraft] = useState<BookEditDraft>();
  const [baseline, setBaseline] = useState<BookEditDraft>();
  const [tab, setTab] = useState<BookEditTab>("book");
  const [mutation, setMutation] = useState<MutationState>(idleMutationState);
  const [coverMutation, setCoverMutation] = useState<MutationState>(idleMutationState);
  const [coverPendingAction, setCoverPendingAction] = useState<"replace" | "clear">();
  const [selectedCoverFile, setSelectedCoverFile] = useState<File>();
  const [coverInputResetKey, setCoverInputResetKey] = useState(0);
  const allowNavigation = useRef(false);
  const book = load.status === "ready" ? load.book : undefined;
  const dirty = Boolean(draft && baseline && !bookEditDraftsEqual(draft, baseline));
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
    if (!draft || !bookId) return;
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

  function cancel() {
    if (dirty && !window.confirm("Discard unsaved Book changes?")) return;
    allowNavigation.current = true;
    const incoming = readIncomingBreadcrumbTrail(location.state);
    const detailTrail = incoming?.at(-1)?.label === "Edit" ? incoming.slice(0, -1) : bookDetailBreadcrumbFallback(book?.title ?? "Book");
    navigate(`/library/books/${encodeURIComponent(bookId)}`, { state: breadcrumbNavigationState(detailTrail) });
  }

  if (load.status === "not-found") return <div className="page-stack book-edit-page"><BookDetailStatePageRegion state="not-found" /></div>;
  if (load.status === "error") return <div className="page-stack book-edit-page"><BookDetailStatePageRegion state="error" error={load.error} onRetry={() => setBookRetry((value) => value + 1)} /></div>;
  if (load.status === "loading" || !draft) return <div className="page-stack book-edit-page"><BookDetailStatePageRegion state="loading" /></div>;
  const readyBook = load.book;

  return <form className="book-edit-page" onSubmit={save}>
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
      <BookEditTabsPageRegion active={tab} onChange={setTab} />
      {tab === "book" ? <BookEditBookPageRegion draft={draft} error={mutation.error} onChange={change} /> : null}
      {tab === "catalog" ? <BookEditCatalogPageRegion draft={draft} error={mutation.error} tags={tags.items} tagsLoading={tags.loading} tagsError={tags.error} onRetryTags={() => setTagRetry((value) => value + 1)} onChange={change} /> : null}
      {tab === "authors-series" ? <BookEditAuthorsSeriesPageRegion draft={draft} error={mutation.error} authors={authors.items} series={series.items} authorsLoading={authors.loading} seriesLoading={series.loading} authorsError={authors.error} seriesError={series.error} returnTo={location.pathname} onRetryAuthors={() => setAuthorRetry((value) => value + 1)} onRetrySeries={() => setSeriesRetry((value) => value + 1)} onChange={change} /> : null}
      {tab === "identifiers" ? <BookEditIdentifiersPageRegion draft={draft} error={mutation.error} onChange={change} /> : null}
      <SaveCancelActionRowComponent state={mutation} submitLabel="Save Book" pendingLabel="Saving..." onCancel={cancel} />
    </main>
  </form>;
}

function loadPicker<T>(request: () => Promise<T[]>, setState: (state: PickerLoad<T>) => void): () => void {
  let active = true;
  setState({ loading: true, items: [] });
  request().then((items) => { if (active) setState({ loading: false, items }); }).catch((error: unknown) => { if (active) setState({ loading: false, items: [], error: normalizeMutationError(error) }); });
  return () => { active = false; };
}

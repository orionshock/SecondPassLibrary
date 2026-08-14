import {
  ApiError,
  buildReadingClientBookUrl,
  getBook,
  isAtLeastLibrarian,
  listAllGroupsForBook,
  listAllShelvesForBook,
  type BookDetail,
} from "@second-pass/spl-api";
import { COMPACT_BOOK_COVER_PREVIEW_SOURCE_LIMIT } from "../../shared/books/bookCoverPreview";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useOutletContext, useParams } from "react-router";

import type { AppOutletContext } from "../../app/layout/AppOrchestrator";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { breadcrumbNavigationState, resolveBreadcrumbTrail } from "../../app/navigation/breadcrumbs";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";
import {
  bookDetailBreadcrumbFallback,
  bookEditBreadcrumbTrail,
  bookGroupBreadcrumbTrail,
  bookGroupPreviewBreadcrumbTrail,
  bookShelfBreadcrumbTrail,
  bookShelfPreviewBreadcrumbTrail,
} from "./bookDetailPresentation";
import { bookDetailQueryFromSearchParams, bookDetailSearchParams, type BookDetailTab } from "./bookTabs";
import { BookDetailHeroPageRegion } from "./regions/BookDetailHeroPageRegion";
import {
  BookDetailSectionsPageRegion,
  type BookGroupsState,
  type BookShelvesState,
} from "./regions/BookDetailSectionsPageRegion";
import { BookDetailStatePageRegion } from "./regions/BookDetailStatePageRegion";
import "./BookDetail.css";

type BookDetailLoadState =
  | { status: "loading" }
  | { status: "ready"; book: BookDetail }
  | { status: "not-found" }
  | { status: "error"; error: Error };

export function BookDetailOrchestrator() {
  const { bookId } = useParams();
  const { currentUser, serverInfo } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const navigate = useNavigate();
  const detailQuery = useMemo(
    () => bookDetailQueryFromSearchParams(
      new URLSearchParams(location.search),
      serverInfo.advancedLibraryGroupsEnabled,
    ),
    [location.search, serverInfo.advancedLibraryGroupsEnabled],
  );
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<BookDetailLoadState>({ status: "loading" });
  const [shelvesLoad, setShelvesLoad] = useState<BookShelvesState>({ status: "idle" });
  const [groupsLoad, setGroupsLoad] = useState<BookGroupsState>({ status: "idle" });
  const shelvesRequestActive = useRef(false);
  const groupsRequestActive = useRef(false);
  const shelvesBookId = useRef<string | undefined>(bookId);
  const groupsBookId = useRef<string | undefined>(bookId);
  const book = load.status === "ready" ? load.book : undefined;
  const breadcrumbFallback = useMemo(
    () => bookDetailBreadcrumbFallback(book?.title ?? "Book"),
    [book?.title],
  );
  usePageBreadcrumbs(breadcrumbFallback);

  useEffect(() => {
    const currentQuery = location.search.startsWith("?") ? location.search.slice(1) : location.search;
    if (currentQuery === detailQuery.query) return;
    navigate({ pathname: location.pathname, search: detailQuery.query }, {
      replace: true,
      state: location.state,
    });
  }, [detailQuery.query, location.pathname, location.search, location.state, navigate]);

  useEffect(() => {
    shelvesBookId.current = bookId;
    groupsBookId.current = bookId;
    shelvesRequestActive.current = false;
    groupsRequestActive.current = false;
    setShelvesLoad({ status: "idle" });
    setGroupsLoad({ status: "idle" });
    if (!bookId) {
      setLoad({ status: "not-found" });
      return;
    }
    let active = true;
    setLoad({ status: "loading" });
    getBook(bookId)
      .then((loadedBook) => { if (active) setLoad({ status: "ready", book: loadedBook }); })
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiError && error.status === 404) setLoad({ status: "not-found" });
        else setLoad({ status: "error", error: normalizeMutationError(error) });
      });
    return () => {
      active = false;
      if (shelvesBookId.current === bookId) shelvesBookId.current = undefined;
      if (groupsBookId.current === bookId) groupsBookId.current = undefined;
    };
  }, [bookId, retry]);

  const loadShelves = useCallback(() => {
    if (!bookId || shelvesRequestActive.current || shelvesLoad.status === "ready") return;
    const requestedBookId = bookId;
    shelvesRequestActive.current = true;
    setShelvesLoad({ status: "loading" });
    listAllShelvesForBook(requestedBookId, COMPACT_BOOK_COVER_PREVIEW_SOURCE_LIMIT)
      .then((shelves) => {
        if (shelvesBookId.current === requestedBookId) setShelvesLoad({ status: "ready", shelves });
      })
      .catch((error: unknown) => {
        if (shelvesBookId.current === requestedBookId) {
          setShelvesLoad({ status: "error", error: normalizeMutationError(error) });
        }
      })
      .finally(() => {
        if (shelvesBookId.current === requestedBookId) shelvesRequestActive.current = false;
      });
  }, [bookId, shelvesLoad.status]);

  const loadGroups = useCallback(() => {
    if (!bookId || groupsRequestActive.current || groupsLoad.status === "ready") return;
    const requestedBookId = bookId;
    groupsRequestActive.current = true;
    setGroupsLoad({ status: "loading" });
    listAllGroupsForBook(requestedBookId, COMPACT_BOOK_COVER_PREVIEW_SOURCE_LIMIT)
      .then((groups) => {
        if (groupsBookId.current === requestedBookId) setGroupsLoad({ status: "ready", groups });
      })
      .catch((error: unknown) => {
        if (groupsBookId.current === requestedBookId) {
          setGroupsLoad({ status: "error", error: normalizeMutationError(error) });
        }
      })
      .finally(() => {
        if (groupsBookId.current === requestedBookId) groupsRequestActive.current = false;
      });
  }, [bookId, groupsLoad.status]);

  useEffect(() => {
    if (load.status === "ready" && detailQuery.tab === "shelves" && shelvesLoad.status === "idle") loadShelves();
  }, [detailQuery.tab, load.status, loadShelves, shelvesLoad.status]);

  useEffect(() => {
    if (load.status === "ready" && detailQuery.tab === "groups" && groupsLoad.status === "idle") loadGroups();
  }, [detailQuery.tab, groupsLoad.status, load.status, loadGroups]);

  function changeSection(tab: BookDetailTab) {
    const parameters = bookDetailSearchParams(new URLSearchParams(location.search), tab);
    navigate({ pathname: location.pathname, search: parameters.toString() }, {
      state: location.state,
    });
  }

  if (load.status === "loading") return <ProductPageShellComponent><BookDetailStatePageRegion state="loading" /></ProductPageShellComponent>;
  if (load.status === "not-found") return <ProductPageShellComponent><BookDetailStatePageRegion state="not-found" /></ProductPageShellComponent>;
  if (load.status === "error") return <ProductPageShellComponent><BookDetailStatePageRegion state="error" error={load.error} onRetry={() => setRetry((value) => value + 1)} /></ProductPageShellComponent>;

  return <ProductPageShellComponent><article className="page-stack book-detail-page">
    <BookDetailHeroPageRegion
      book={load.book}
      readingClientBookUrl={serverInfo.readingClientBaseUrl && load.book.file
        ? buildReadingClientBookUrl(serverInfo.readingClientBaseUrl, load.book.id)
        : undefined}
      canEdit={isAtLeastLibrarian(currentUser)}
      editNavigationState={breadcrumbNavigationState(bookEditBreadcrumbTrail(resolveBreadcrumbTrail(location.state, breadcrumbFallback), load.book.id, load.book.title))}
    />
    <BookDetailSectionsPageRegion
      book={load.book}
      advancedGroupsEnabled={serverInfo.advancedLibraryGroupsEnabled}
      activeSection={detailQuery.tab}
      shelvesState={shelvesLoad}
      groupsState={groupsLoad}
      shelfNavigationState={(shelf) => breadcrumbNavigationState(bookShelfBreadcrumbTrail(
        resolveBreadcrumbTrail(location.state, breadcrumbFallback),
        load.book.id,
        load.book.title,
        shelf.name,
      ))}
      shelfBookNavigationState={(shelf, preview) => breadcrumbNavigationState(bookShelfPreviewBreadcrumbTrail(
        resolveBreadcrumbTrail(location.state, breadcrumbFallback),
        load.book.id,
        load.book.title,
        shelf.id,
        shelf.name,
        preview.title,
      ))}
      groupNavigationState={(group) => breadcrumbNavigationState(bookGroupBreadcrumbTrail(
        resolveBreadcrumbTrail(location.state, breadcrumbFallback),
        load.book.id,
        load.book.title,
        group.name,
        group.isPublicGroup,
      ))}
      groupBookNavigationState={(group, preview) => breadcrumbNavigationState(bookGroupPreviewBreadcrumbTrail(
        resolveBreadcrumbTrail(location.state, breadcrumbFallback),
        load.book.id,
        load.book.title,
        group.id,
        group.name,
        preview.title,
        group.isPublicGroup,
      ))}
      onSectionChange={changeSection}
      onRetryShelves={loadShelves}
      onRetryGroups={loadGroups}
    />
  </article></ProductPageShellComponent>;
}

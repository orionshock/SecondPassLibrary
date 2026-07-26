import {
  ApiError,
  getBook,
  isAtLeastLibrarian,
  listAllShelvesForBook,
  type BookDetail,
} from "@second-pass/spl-api";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useOutletContext, useParams } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { breadcrumbNavigationState, resolveBreadcrumbTrail } from "../../app/navigation/breadcrumbs";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { bookDetailBreadcrumbFallback, bookEditBreadcrumbTrail, bookShelfBreadcrumbTrail } from "./bookDetailPresentation";
import { BookDetailHeroPageRegion } from "./regions/BookDetailHeroPageRegion";
import {
  BookDetailSectionsPageRegion,
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
  const { currentUser } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<BookDetailLoadState>({ status: "loading" });
  const [shelvesLoad, setShelvesLoad] = useState<BookShelvesState>({ status: "idle" });
  const shelvesRequestActive = useRef(false);
  const shelvesBookId = useRef<string | undefined>(bookId);
  const book = load.status === "ready" ? load.book : undefined;
  const breadcrumbFallback = useMemo(
    () => bookDetailBreadcrumbFallback(book?.title ?? "Book"),
    [book?.title],
  );
  usePageBreadcrumbs(breadcrumbFallback);

  useEffect(() => {
    shelvesBookId.current = bookId;
    shelvesRequestActive.current = false;
    setShelvesLoad({ status: "idle" });
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
    };
  }, [bookId, retry]);

  const loadShelves = useCallback(() => {
    if (!bookId || shelvesRequestActive.current || shelvesLoad.status === "ready") return;
    const requestedBookId = bookId;
    shelvesRequestActive.current = true;
    setShelvesLoad({ status: "loading" });
    listAllShelvesForBook(requestedBookId)
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

  if (load.status === "loading") return <div className="page-stack book-detail-page"><BookDetailStatePageRegion state="loading" /></div>;
  if (load.status === "not-found") return <div className="page-stack book-detail-page"><BookDetailStatePageRegion state="not-found" /></div>;
  if (load.status === "error") return <div className="page-stack book-detail-page"><BookDetailStatePageRegion state="error" error={load.error} onRetry={() => setRetry((value) => value + 1)} /></div>;

  return <article className="page-stack book-detail-page">
    <BookDetailHeroPageRegion
      book={load.book}
      canEdit={isAtLeastLibrarian(currentUser)}
      editNavigationState={breadcrumbNavigationState(bookEditBreadcrumbTrail(resolveBreadcrumbTrail(location.state, breadcrumbFallback), load.book.id, load.book.title))}
    />
    <BookDetailSectionsPageRegion
      book={load.book}
      advancedGroupsEnabled={currentUser.advancedLibraryGroupsEnabled}
      shelvesState={shelvesLoad}
      shelfNavigationState={(shelfName) => breadcrumbNavigationState(bookShelfBreadcrumbTrail(
        resolveBreadcrumbTrail(location.state, breadcrumbFallback),
        load.book.id,
        load.book.title,
        shelfName,
      ))}
      onLoadShelves={loadShelves}
      onRetryShelves={loadShelves}
    />
  </article>;
}

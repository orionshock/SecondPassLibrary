import type { ShelfEditorItem, ShelfEditorItemsPage } from "@second-pass/spl-api";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { RemoveIconButton } from "../../../components/icons/RemoveIconButton";
import { Button, ErrorPanel, IconButton } from "../../../components/ui";
import { CompactBookRowComponent } from "../../../shared/books/CompactBookRowComponent";
import { PagerComponent } from "../../../shared/pagination/PagerComponent";
import { shelfBookBreadcrumbs } from "../shelvesBreadcrumbs";

export function ShelfEditBooksPageRegion({ shelfId, shelfName, page, pageNumber, pageSize, loading, error, pendingItemId, pendingAction, controlsDisabled, onMove, onMoveTo, onRemove, onPageChange, onPageSizeChange, onRetry }: {
  shelfId: string;
  shelfName: string;
  page?: ShelfEditorItemsPage;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  pendingItemId?: string;
  pendingAction?: "move" | "remove";
  controlsDisabled?: boolean;
  onMove: (itemId: string, move: "up" | "down") => void;
  onMoveTo: (itemId: string, position: number) => void;
  onRemove: (item: ShelfEditorItem) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="shelf-edit-section-state" aria-live="polite" aria-busy="true">Loading books...</section>;
  if (!page && error) return <section className="shelf-edit-section-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;

  const visibleItems = page.items.filter((item) => !item.unavailable);
  return <section className="shelf-edit-books-region" aria-label="Shelf books" aria-busy={loading}>
    {error ? <div className="shelf-edit-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    <p className="shelf-edit-item-counts">
      {page.visibleItemCount} visible · {page.count} total
      {page.unavailableItemCount ? ` · ${page.unavailableItemCount} unavailable` : ""}
    </p>
    {page.items.length === 0 ? <p className="muted">This shelf has no books.</p> : <div className="shelf-edit-book-rows">
      {page.items.map((item) => item.unavailable
        ? <UnavailableShelfItemRow
          key={item.id}
          item={item}
          disabled={controlsDisabled || Boolean(pendingItemId)}
          removing={pendingItemId === item.id && pendingAction === "remove"}
          onRemove={onRemove}
        />
        : <VisibleShelfItemRow
          key={item.id}
          item={item}
          shelfId={shelfId}
          shelfName={shelfName}
          canMoveUp={hasVisibleBefore(item, visibleItems, page)}
          canMoveDown={hasVisibleAfter(item, visibleItems, page)}
          positionCount={page.count}
          directPositioningDisabled={page.unavailableItemCount > 0}
          disabled={controlsDisabled || Boolean(pendingItemId)}
          moving={pendingItemId === item.id && pendingAction === "move"}
          removing={pendingItemId === item.id && pendingAction === "remove"}
          onMove={onMove}
          onMoveTo={onMoveTo}
          onRemove={onRemove}
        />)}
    </div>}
    <PagerComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Items" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
  </section>;
}

function VisibleShelfItemRow({ item, shelfId, shelfName, canMoveUp, canMoveDown, positionCount, directPositioningDisabled, disabled, moving, removing, onMove, onMoveTo, onRemove }: {
  item: Extract<ShelfEditorItem, { unavailable: false }>;
  shelfId: string;
  shelfName: string;
  canMoveUp: boolean;
  canMoveDown: boolean;
  positionCount: number;
  directPositioningDisabled: boolean;
  disabled: boolean;
  moving: boolean;
  removing: boolean;
  onMove: (itemId: string, move: "up" | "down") => void;
  onMoveTo: (itemId: string, position: number) => void;
  onRemove: (item: ShelfEditorItem) => void;
}) {
  return <div className="shelf-edit-book-row" aria-busy={moving || undefined}>
    <span className="shelf-edit-position" aria-label={`Shelf position ${item.position + 1}`}>#{item.position + 1}</span>
    <CompactBookRowComponent
      book={item.book}
      detailPath={`/library/books/${encodeURIComponent(item.book.id)}`}
      navigationState={breadcrumbNavigationState(shelfBookBreadcrumbs(shelfId, shelfName, item.book.title))}
      actions={<>
        <ShelfPositionSelectComponent
          bookTitle={item.book.title}
          position={item.position}
          positionCount={positionCount}
          disabled={disabled || directPositioningDisabled}
          onChange={(position) => onMoveTo(item.id, position)}
        />
        <IconButton type="button" aria-label={`Move ${item.book.title} up`} title="Move up" disabled={disabled || !canMoveUp} onClick={() => onMove(item.id, "up")}><MaterialIcon name="arrow_upward" /></IconButton>
        <IconButton type="button" aria-label={`Move ${item.book.title} down`} title="Move down" disabled={disabled || !canMoveDown} onClick={() => onMove(item.id, "down")}><MaterialIcon name="arrow_downward" /></IconButton>
        <RemoveIconButton type="button" label={`Remove ${item.book.title} from shelf`} disabled={disabled} title={removing ? "Removing" : "Remove from shelf"} onClick={() => onRemove(item)} />
      </>}
    />
  </div>;
}

export function ShelfPositionSelectComponent({ bookTitle, position, positionCount, disabled, onChange }: {
  bookTitle: string;
  position: number;
  positionCount: number;
  disabled: boolean;
  onChange: (position: number) => void;
}) {
  return <label className="shelf-edit-move-to">
    <span>Move To</span>
    <select
      aria-label={`Move ${bookTitle} to position`}
      value={position}
      disabled={disabled}
      onChange={(event) => {
        const nextPosition = Number(event.target.value);
        if (nextPosition !== position) onChange(nextPosition);
      }}
    >
      {Array.from({ length: positionCount }, (_, optionPosition) => <option
        key={optionPosition}
        value={optionPosition}
        disabled={optionPosition === position}
      >{optionPosition + 1}</option>)}
    </select>
  </label>;
}

function UnavailableShelfItemRow({ item, disabled, removing, onRemove }: {
  item: Extract<ShelfEditorItem, { unavailable: true }>;
  disabled: boolean;
  removing: boolean;
  onRemove: (item: ShelfEditorItem) => void;
}) {
  return <div className="shelf-edit-book-row shelf-edit-unavailable-row" aria-label={`Unavailable shelf item at position ${item.position + 1}`}>
    <span className="shelf-edit-position">#{item.position + 1}</span>
    <div className="shelf-edit-unavailable-identity"><MaterialIcon name="lock" /><span>Unavailable item</span></div>
    <div className="shelf-edit-item-actions">
      <RemoveIconButton type="button" label="Remove unavailable item" disabled={disabled} title={removing ? "Removing" : "Remove unavailable item"} onClick={() => onRemove(item)} />
    </div>
  </div>;
}

function hasVisibleBefore(
  item: Extract<ShelfEditorItem, { unavailable: false }>,
  visibleItems: Array<Extract<ShelfEditorItem, { unavailable: false }>>,
  page: ShelfEditorItemsPage,
): boolean {
  return visibleItems.findIndex(({ id }) => id === item.id) > 0 || Boolean(page.previous);
}

function hasVisibleAfter(
  item: Extract<ShelfEditorItem, { unavailable: false }>,
  visibleItems: Array<Extract<ShelfEditorItem, { unavailable: false }>>,
  page: ShelfEditorItemsPage,
): boolean {
  return visibleItems.findIndex(({ id }) => id === item.id) < visibleItems.length - 1 || Boolean(page.next);
}

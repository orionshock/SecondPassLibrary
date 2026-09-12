import type { CatalogTag } from "@second-pass/spl-api";
import { useEffect, useRef, useState, type CSSProperties, type RefObject } from "react";

import { Button, ErrorPanel } from "../../../components/UiPrimitives";

export const CATALOG_TAG_MINIMUM_VISIBLE_ROWS = 15;

export function CatalogTagRailPageRegion({ tags, activeTag, activeTagDetails, loading, error, onTagChange, onRetry }: {
  tags?: CatalogTag[];
  activeTag?: string;
  activeTagDetails?: CatalogTag;
  loading: boolean;
  error?: Error;
  onTagChange: (tag?: string) => void;
  onRetry: () => void;
}) {
  const desktopActiveTag = useRef<HTMLButtonElement>(null);
  const mobileActiveTag = useRef<HTMLButtonElement>(null);
  const [tagSearch, setTagSearch] = useState("");

  useEffect(() => {
    for (const button of [desktopActiveTag.current, mobileActiveTag.current]) {
      button?.scrollIntoView?.({ block: "nearest" });
    }
  }, [activeTag, tagSearch, tags]);

  const allTagsButton = <button type="button" className={`catalog-tag-rail__all${!activeTag ? " active" : ""}`} aria-pressed={!activeTag} onClick={() => onTagChange(undefined)}>
    All tags
  </button>;
  const tagSearchInput = <input
    className="catalog-tag-rail__search"
    type="search"
    aria-label="Search Catalog Tags"
    placeholder="Search tags..."
    value={tagSearch}
    onChange={(event) => setTagSearch(event.target.value)}
  />;

  return <aside
    className="catalog-tag-rail"
    aria-label="Catalog Tags"
    style={{ "--catalog-tag-minimum-visible-rows": CATALOG_TAG_MINIMUM_VISIBLE_ROWS } as CSSProperties}
  >
    <h2>Catalog Tags</h2>
    <div className="catalog-tag-rail__desktop">
      {tagSearchInput}
      {allTagsButton}
      {tagList(tags, activeTag, activeTagDetails, tagSearch, loading, error, onTagChange, onRetry, desktopActiveTag)}
    </div>
    <details className="catalog-tag-rail__mobile">
      <summary>{activeTag
        ? tags?.find(({ slug }) => slug === activeTag)?.name ?? activeTagDetails?.name ?? "Catalog Tags"
        : "All Catalog Tags"}</summary>
      <div className="catalog-tag-rail__mobile-body">
        {tagSearchInput}
        {allTagsButton}
        {tagList(tags, activeTag, activeTagDetails, tagSearch, loading, error, onTagChange, onRetry, mobileActiveTag)}
      </div>
    </details>
  </aside>;
}

function tagList(
  tags: CatalogTag[] | undefined,
  activeTag: string | undefined,
  activeTagDetails: CatalogTag | undefined,
  tagSearch: string,
  loading: boolean,
  error: Error | undefined,
  onTagChange: (tag?: string) => void,
  onRetry: () => void,
  activeTagRef: RefObject<HTMLButtonElement | null>,
) {
  const contextualIds = new Set(tags?.map(({ id }) => id));
  const availableTags = activeTagDetails && activeTag === activeTagDetails.slug && !contextualIds.has(activeTagDetails.id)
    ? [...(tags ?? []), activeTagDetails]
    : tags;
  const normalizedSearch = tagSearch.trim().toLowerCase();
  const displayedTags = normalizedSearch
    ? availableTags?.filter((tag) => (
      tag.slug === activeTag || tag.name.toLowerCase().includes(normalizedSearch)
    ))
    : availableTags;
  return <div
    className="catalog-tag-rail__list"
    data-minimum-visible-rows={CATALOG_TAG_MINIMUM_VISIBLE_ROWS}
  >
    {loading && !tags ? <p className="catalog-tag-rail__state" aria-live="polite">Loading Catalog Tags...</p> : null}
    {error && !tags ? <div className="catalog-tag-rail__state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry tags</Button></div> : null}
    {displayedTags?.map((tag) => {
      const active = activeTag === tag.slug;
      return <button
        key={tag.id}
        ref={active ? activeTagRef : undefined}
        type="button"
        className={active ? "active" : ""}
        aria-pressed={active}
        onClick={() => onTagChange(catalogTagSelection(activeTag, tag.slug))}
      >
        {contextualIds.has(tag.id) ? <span className="catalog-tag-rail__count">({tag.bookCount})</span> : null}
        <span className="catalog-tag-rail__name" title={tag.name}>{tag.name}</span>
      </button>;
    })}
  </div>;
}

export function catalogTagSelection(activeTag: string | undefined, selectedTag: string): string | undefined {
  return activeTag === selectedTag ? undefined : selectedTag;
}

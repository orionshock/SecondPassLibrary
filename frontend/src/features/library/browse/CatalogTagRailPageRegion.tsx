import type { CatalogTag } from "@second-pass/spl-api";
import { useEffect, useRef, type CSSProperties, type RefObject } from "react";

import { Button, ErrorPanel } from "../../../components/UiPrimitives";

export const CATALOG_TAG_MINIMUM_VISIBLE_ROWS = 15;

export function CatalogTagRailPageRegion({ tags, activeTag, loading, error, onTagChange, onRetry }: {
  tags?: CatalogTag[];
  activeTag?: string;
  loading: boolean;
  error?: Error;
  onTagChange: (tag?: string) => void;
  onRetry: () => void;
}) {
  const desktopActiveTag = useRef<HTMLButtonElement>(null);
  const mobileActiveTag = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    for (const button of [desktopActiveTag.current, mobileActiveTag.current]) {
      button?.scrollIntoView?.({ block: "nearest" });
    }
  }, [activeTag, tags]);

  const allTagsButton = <button type="button" className={`catalog-tag-rail__all${!activeTag ? " active" : ""}`} aria-pressed={!activeTag} onClick={() => onTagChange(undefined)}>
    All tags
  </button>;

  return <aside
    className="catalog-tag-rail"
    aria-label="Catalog Tags"
    style={{ "--catalog-tag-minimum-visible-rows": CATALOG_TAG_MINIMUM_VISIBLE_ROWS } as CSSProperties}
  >
    <h2>Catalog Tags</h2>
    <div className="catalog-tag-rail__desktop">
      {allTagsButton}
      {tagList(tags, activeTag, loading, error, onTagChange, onRetry, desktopActiveTag)}
    </div>
    <details className="catalog-tag-rail__mobile">
      <summary>{activeTag && tags ? tags.find(({ slug }) => slug === activeTag)?.name ?? "Catalog Tags" : "All Catalog Tags"}</summary>
      <div className="catalog-tag-rail__mobile-body">
        {allTagsButton}
        {tagList(tags, activeTag, loading, error, onTagChange, onRetry, mobileActiveTag)}
      </div>
    </details>
  </aside>;
}

function tagList(
  tags: CatalogTag[] | undefined,
  activeTag: string | undefined,
  loading: boolean,
  error: Error | undefined,
  onTagChange: (tag?: string) => void,
  onRetry: () => void,
  activeTagRef: RefObject<HTMLButtonElement | null>,
) {
  return <div
    className="catalog-tag-rail__list"
    data-minimum-visible-rows={CATALOG_TAG_MINIMUM_VISIBLE_ROWS}
  >
    {loading && !tags ? <p className="catalog-tag-rail__state" aria-live="polite">Loading Catalog Tags...</p> : null}
    {error && !tags ? <div className="catalog-tag-rail__state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry tags</Button></div> : null}
    {tags?.map((tag) => {
      const active = activeTag === tag.slug;
      return <button
        key={tag.id}
        ref={active ? activeTagRef : undefined}
        type="button"
        className={active ? "active" : ""}
        aria-pressed={active}
        onClick={() => onTagChange(catalogTagSelection(activeTag, tag.slug))}
      >
        <span className="catalog-tag-rail__count">({tag.bookCount})</span>
        <span className="catalog-tag-rail__name" title={tag.name}>{tag.name}</span>
      </button>;
    })}
  </div>;
}

export function catalogTagSelection(activeTag: string | undefined, selectedTag: string): string | undefined {
  return activeTag === selectedTag ? undefined : selectedTag;
}

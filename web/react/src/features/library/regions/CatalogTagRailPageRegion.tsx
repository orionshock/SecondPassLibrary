import type { CatalogTag } from "@second-pass/spl-api";

import { Button, ErrorPanel } from "../../../components/ui";

export function CatalogTagRailPageRegion({ tags, activeTag, loading, error, onTagChange, onRetry }: {
  tags?: CatalogTag[];
  activeTag?: string;
  loading: boolean;
  error?: Error;
  onTagChange: (tag?: string) => void;
  onRetry: () => void;
}) {
  const content = <div className="catalog-tag-rail__content">
    <button type="button" className={!activeTag ? "active" : ""} aria-pressed={!activeTag} onClick={() => onTagChange(undefined)}>
      <span>All tags</span>
    </button>
    {loading && !tags ? <p className="catalog-tag-rail__state" aria-live="polite">Loading Catalog Tags...</p> : null}
    {error && !tags ? <div className="catalog-tag-rail__state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry tags</Button></div> : null}
    {tags?.map((tag) => {
      const active = activeTag === tag.slug;
      return <button key={tag.id} type="button" className={active ? "active" : ""} aria-pressed={active} onClick={() => onTagChange(catalogTagSelection(activeTag, tag.slug))}>
        <span className="catalog-tag-rail__name" title={tag.name}>{tag.name}</span><span className="catalog-tag-rail__count">{tag.bookCount}</span>
      </button>;
    })}
  </div>;

  return <aside className="catalog-tag-rail" aria-label="Catalog Tags">
    <h2>Catalog Tags</h2>
    <div className="catalog-tag-rail__desktop">{content}</div>
    <details className="catalog-tag-rail__mobile"><summary>{activeTag && tags ? tags.find(({ slug }) => slug === activeTag)?.name ?? "Catalog Tags" : "All Catalog Tags"}</summary>{content}</details>
  </aside>;
}

export function catalogTagSelection(activeTag: string | undefined, selectedTag: string): string | undefined {
  return activeTag === selectedTag ? undefined : selectedTag;
}

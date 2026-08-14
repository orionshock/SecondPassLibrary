import type { LibrarySeries, Page } from "@second-pass/spl-api";

import { Button, ErrorPanel } from "../../../components/ui";
import { Pager } from "../../../shared/pagination/Pager";
import { SeriesRow } from "../components/SeriesRow";

export function SeriesListPageRegion({ page, pageNumber, pageSize, loading, error, searching, tagged, libraryPath, contextPathFor, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<LibrarySeries>;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  searching: boolean;
  tagged: boolean;
  libraryPath: string;
  contextPathFor: (series: LibrarySeries) => string;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="library-list-state" aria-live="polite" aria-busy="true">Loading series...</section>;
  if (!page && error) return <section className="library-list-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;
  return <section className={`library-axis-list-region${loading ? " library-axis-list-region--loading" : ""}`} aria-label="Series" aria-busy={loading}>
    {error ? <div className="library-list-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page.items.length === 0
      ? <p className="library-list-state muted">{seriesEmptyCopy(searching, tagged)}</p>
      : <div className="library-axis-list-region__rows">{page.items.map((series) => <SeriesRow key={series.id} series={series} libraryPath={libraryPath} contextPath={contextPathFor(series)} />)}</div>}
    <Pager page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Series" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
  </section>;
}

export function seriesEmptyCopy(searching: boolean, tagged: boolean): string {
  if (searching && tagged) return "No series match this search within this Catalog Tag.";
  if (searching) return "No series match this search.";
  if (tagged) return "No series for this Catalog Tag.";
  return "No series.";
}

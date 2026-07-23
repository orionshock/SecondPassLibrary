import { describe, expect, it } from "vitest";

import { listAllCatalogTags, listBooks, listCatalogTags } from "@second-pass/spl-api";
import type { ApiClient } from "../../packages/spl-api/src/client";

const compactWireBook = {
  id: "book-1", title: "The Book", sort_title: "Book, The", subtitle: "Hidden subtitle",
  authors: [{ id: "author-1", name: "Ada Author" }],
  series: { id: "series-1", name: "A Series", sort_name: "Series, A", series_index: "2.00" },
  catalog_tags: [{ id: "tag-1", name: "Fantasy", slug: "fantasy" }],
  language: "en", publisher: "A Press", published_year: 2020, published_month: 3, published_day: null,
  published_date_precision: "month", cover_url: "/media/cover.jpg", file_format: "epub",
  groups: [{ id: "secret" }], identifiers: [{ scheme: "isbn", value: "secret" }],
  file: { checksum: "secret", storage_path: "secret" }, description: "secret", source_filename: "secret.epub",
};

describe("Library SDK", () => {
  it("maps Books-axis queries and compact wire fields", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return { count: 1, next: null, previous: null, results: [compactWireBook] } as T;
    } };

    const page = await listBooks({ q: " Book ", tag: "fantasy", ordering: "-author", page: 2, pageSize: 30 }, client);

    expect(calls).toEqual(["/api/v1/library/books/?q=Book&tag=fantasy&ordering=-author&page=2&page_size=30"]);
    expect(page.items[0]).toEqual({
      id: "book-1", title: "The Book", sortTitle: "Book, The", subtitle: "Hidden subtitle",
      authors: [{ id: "author-1", name: "Ada Author" }],
      series: { id: "series-1", name: "A Series", sortName: "Series, A", seriesIndex: "2.00" },
      catalogTags: [{ id: "tag-1", name: "Fantasy", slug: "fantasy" }],
      language: "en", publisher: "A Press", publishedYear: 2020, publishedMonth: 3, publishedDay: null,
      publishedDatePrecision: "month", coverUrl: "/media/cover.jpg", fileFormat: "epub",
    });
    for (const field of ["groups", "identifiers", "file", "checksum", "description", "storagePath", "sourceFilename"]) {
      expect(page.items[0]).not.toHaveProperty(field);
    }
  });

  it("maps a Catalog Tag page and viewer-scoped book count", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return { count: 1, next: null, previous: null, results: [{ id: "tag", name: "Fantasy", slug: "fantasy", book_count: 7 }] } as T;
    } };
    await expect(listCatalogTags({ ordering: "-book_count", page: 2, pageSize: 50 }, client)).resolves.toMatchObject({
      items: [{ id: "tag", name: "Fantasy", slug: "fantasy", bookCount: 7 }],
    });
    expect(calls).toEqual(["/api/v1/library/tags/?ordering=-book_count&page=2&page_size=50"]);
  });

  it("requests 200 Catalog Tags at a time and follows every next page", async () => {
    const calls: string[] = [];
    const pages = [
      { count: 2, next: "/api/v1/library/tags/?ordering=name&page=2&page_size=200", previous: null, results: [{ id: "1", name: "A", slug: "a", book_count: 1 }] },
      { count: 2, next: null, previous: "previous", results: [{ id: "2", name: "B", slug: "b", book_count: 2 }] },
    ];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return pages.shift() as T;
    } };
    await expect(listAllCatalogTags(client)).resolves.toEqual([
      { id: "1", name: "A", slug: "a", bookCount: 1 },
      { id: "2", name: "B", slug: "b", bookCount: 2 },
    ]);
    expect(calls).toEqual([
      "/api/v1/library/tags/?ordering=name&page_size=200",
      "/api/v1/library/tags/?ordering=name&page=2&page_size=200",
    ]);
  });
});

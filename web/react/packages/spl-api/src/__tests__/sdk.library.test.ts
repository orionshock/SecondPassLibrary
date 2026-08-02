import { describe, expect, it } from "vitest";

import { ApiError, clearBookCover, createAuthor, createSeries, deleteAuthor, deleteSeries, getAuthor, getBook, getSeries, listAllAuthors, listAllCatalogTags, listAllSeries, listAuthors, listBooks, listCatalogTags, listSeries, replaceBookCover, searchLibraryBooks, updateAuthor, updateBook, updateSeries } from "@second-pass/spl-api";
import { createApiClient, type ApiClient } from "../client";

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
  it("uses the shared session transport for Author and Series DELETE requests", async () => {
    const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const fetchImplementation: typeof fetch = async (input, init) => {
      calls.push({ input, init });
      return new Response(null, { status: 204 });
    };
    const client = createApiClient(fetchImplementation, () => "csrf-token");

    await deleteAuthor("author/id", client);
    await deleteSeries("series/id", client);

    expect(calls.map(({ input, init }) => [input, init?.method])).toEqual([
      ["/api/v1/library/authors/author%2Fid/", "DELETE"],
      ["/api/v1/library/series/series%2Fid/", "DELETE"],
    ]);
    for (const { init } of calls) {
      expect(init?.credentials).toBe("same-origin");
      expect(new Headers(init?.headers).get("X-CSRFToken")).toBe("csrf-token");
    }
  });

  it("maps Author lifecycle detail/create/update contracts without admitting extra fields", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => {
      calls.push({ path, init });
      return { id: "author", name: "Ada", sort_name: "Author, Ada", biography: "Bio", book_count: 2, normalized_name: "hidden", preview_books: undefined } as T;
    } };
    const input = { name: "Ada", sortName: "Author, Ada", biography: "Bio", ...({ normalizedName: "hidden", bookCount: 99, groups: [] } as object) };

    await expect(getAuthor("author/id", client)).resolves.toMatchObject({ id: "author", sortName: "Author, Ada", biography: "Bio" });
    await createAuthor(input, client);
    await updateAuthor("author/id", input, client);
    await deleteAuthor("author/id", client);

    expect(calls.map(({ path }) => path)).toEqual([
      "/api/v1/library/authors/author%2Fid/?include_preview_books=true",
      "/api/v1/library/authors/",
      "/api/v1/library/authors/author%2Fid/",
      "/api/v1/library/authors/author%2Fid/",
    ]);
    expect(calls.slice(1, 3).map(({ init }) => [init?.method, JSON.parse(String(init?.body))])).toEqual([
      ["POST", { name: "Ada", sort_name: "Author, Ada", biography: "Bio" }],
      ["PATCH", { name: "Ada", sort_name: "Author, Ada", biography: "Bio" }],
    ]);
    expect(calls[3]?.init).toEqual({ method: "DELETE" });
  });

  it("maps Series lifecycle contracts and operation field errors", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => {
      calls.push({ path, init });
      return { id: "series", name: "Saga", sort_name: "Saga", summary: "Summary", book_count: 1 } as T;
    } };
    const input = { name: "Saga", sortName: "Saga", summary: "Summary", ...({ books: [], previewBooks: [] } as object) };

    await expect(getSeries("series/id", client)).resolves.toMatchObject({ id: "series", sortName: "Saga", summary: "Summary" });
    await createSeries(input, client);
    await updateSeries("series/id", input, client);
    await deleteSeries("series/id", client);
    expect(calls.map(({ path }) => path)).toEqual([
      "/api/v1/library/series/series%2Fid/?include_preview_books=true",
      "/api/v1/library/series/",
      "/api/v1/library/series/series%2Fid/",
      "/api/v1/library/series/series%2Fid/",
    ]);
    expect(calls.slice(1, 3).map(({ init }) => [init?.method, JSON.parse(String(init?.body))])).toEqual([
      ["POST", { name: "Saga", sort_name: "Saga", summary: "Summary" }],
      ["PATCH", { name: "Saga", sort_name: "Saga", summary: "Summary" }],
    ]);
    expect(calls[3]?.init).toEqual({ method: "DELETE" });

    const failing: ApiClient = { request: async () => { throw new ApiError("Invalid.", 400, { fields: { sort_name: ["Invalid sort name."] } }); } };
    await expect(updateSeries("series", input, failing)).rejects.toMatchObject({
      fields: { sortName: ["Invalid sort name."] },
    });

    const seriesConflict = new ApiError("Series cannot be deleted because 1 Book is attached.", 409, {
      code: "series_has_books",
    });
    const seriesConflicting: ApiClient = { request: async () => { throw seriesConflict; } };
    await expect(deleteSeries("series", seriesConflicting)).rejects.toBe(seriesConflict);
    const authorConflict = new ApiError("Author cannot be deleted because 2 Books are attached.", 409, {
      code: "author_has_books",
    });
    const authorConflicting: ApiClient = { request: async () => { throw authorConflict; } };
    await expect(deleteAuthor("author", authorConflicting)).rejects.toMatchObject({
      status: 409,
      code: "author_has_books",
    });
  });

  it("PATCHes only mapped Book Edit fields, including exact identifier replacements", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => {
      calls.push({ path, init });
      return {
        id: "book", title: "Saved", sort_title: "", subtitle: "", authors: [], series: null,
        language: "", publisher: "", published_year: null, published_month: null, published_day: null,
        published_date_precision: "", cover_url: null, description: "", identifiers: [], catalog_tags: [], file: null, groups: [],
      } as T;
    } };
    await updateBook("book/id", {
      title: "Saved", sortTitle: "", publishedYear: null, authorIds: [], seriesId: null,
      seriesIndex: null, identifiers: [{
        scheme: "doi", value: "10.1000/example",
        ...({ id: "forbidden", key: "forbidden", normalizedValue: "forbidden", randomField: "forbidden" } as object),
      }], catalogTagNames: [],
      ...({ groups: ["forbidden"], checksum: "forbidden", storage: "forbidden", cover: "forbidden", coverUrl: "forbidden" } as object),
    }, client);
    await updateBook("book", { title: "Unchanged", identifiers: undefined }, client);
    await updateBook("book", { title: "Cleared", identifiers: [] }, client);
    expect(calls[0]?.path).toBe("/api/v1/library/books/book%2Fid/");
    expect(calls[0]?.init?.method).toBe("PATCH");
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({
      title: "Saved", sort_title: "", published_year: null, authors: [], series: null, series_index: null,
      identifiers: [{ scheme: "doi", value: "10.1000/example" }], catalog_tags: [],
    });
    expect(JSON.parse(String(calls[1]?.init?.body))).toEqual({ title: "Unchanged" });
    expect(JSON.parse(String(calls[2]?.init?.body))).toEqual({ title: "Cleared", identifiers: [] });

    const failing: ApiClient = { request: async () => { throw new ApiError("Invalid.", 400, { fields: { authors: ["Bad Author"], series: ["Bad Series"], catalogTags: ["Bad Tag"] } }); } };
    await expect(updateBook("book", { title: "Book" }, failing)).rejects.toMatchObject({
      fields: { authorIds: ["Bad Author"], seriesId: ["Bad Series"], catalogTagNames: ["Bad Tag"] },
    });
  });

  it("uses the dedicated multipart and DELETE Book cover contracts", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const wireBook = {
      id: "book", title: "Book", sort_title: "Book", subtitle: "", authors: [], series: null,
      language: "", publisher: "", published_year: null, published_month: null, published_day: null,
      published_date_precision: "", cover_url: "/media/new-cover.jpg", description: "",
      identifiers: [], catalog_tags: [], file: null, groups: [],
    };
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => {
      calls.push({ path, init });
      return wireBook as T;
    } };
    const file = new File(["cover"], "cover.jpg", { type: "image/jpeg" });

    await expect(replaceBookCover("book/id", file, client)).resolves.toMatchObject({
      id: "book", sortTitle: "Book", coverUrl: "/media/new-cover.jpg",
    });
    await expect(clearBookCover("book/id", client)).resolves.toMatchObject({ id: "book" });

    expect(calls.map(({ path, init }) => [path, init?.method])).toEqual([
      ["/api/v1/library/books/book%2Fid/cover/", "POST"],
      ["/api/v1/library/books/book%2Fid/cover/", "DELETE"],
    ]);
    const replaceInit = calls[0]!.init!;
    expect(replaceInit.headers).toBeUndefined();
    expect([...((replaceInit.body as FormData).entries())]).toEqual([["cover", file]]);
    expect(calls[1]!.init?.body).toBeUndefined();

    const error = new ApiError("Invalid cover.", 400, { fields: { cover: ["Choose another image."] } });
    const failing: ApiClient = { request: async () => { throw error; } };
    await expect(replaceBookCover("book", file, failing)).rejects.toBe(error);
    expect(error.fields).toEqual({ cover: ["Choose another image."] });
  });

  it("loads every Author and Series picker page through the role-scoped contract", async () => {
    const calls: string[] = [];
    const responses = [
      { count: 2, next: "/api/v1/library/authors/?ordering=name&page=2&page_size=200", previous: null, results: [{ id: "a1", name: "A", sort_name: "A", biography: "", book_count: 1 }] },
      { count: 2, next: null, previous: "previous", results: [{ id: "a2", name: "B", sort_name: "B", biography: "", book_count: 0 }] },
      { count: 1, next: null, previous: null, results: [{ id: "s1", name: "S", sort_name: "S", summary: "", book_count: 1 }] },
    ];
    const client: ApiClient = { request: async <T>(path: string) => { calls.push(path); return responses.shift() as T; } };
    await expect(listAllAuthors(client)).resolves.toHaveLength(2);
    await expect(listAllSeries(client)).resolves.toHaveLength(1);
    expect(calls).toEqual([
      "/api/v1/library/authors/?ordering=name&page_size=200",
      "/api/v1/library/authors/?ordering=name&page=2&page_size=200",
      "/api/v1/library/series/?ordering=name&page_size=200",
    ]);
  });
  it("maps the explicit Book Detail contract without admitting storage or provenance fields", async () => {
    const calls: string[] = [];
    const wireBook = {
      id: "book-1", title: "The Book", sort_title: "Book, The", subtitle: "A subtitle",
      authors: [{ id: "author-1", name: "Ada Author", normalized_name: "hidden" }],
      series: { id: "series-1", name: "A Series", sort_name: "Series, A", series_index: "2.00", summary: "hidden" },
      language: "en", publisher: "A Press", published_year: 2020, published_month: 3, published_day: null,
      published_date_precision: "month", cover_url: "/media/cover.jpg", description: "Description",
      identifiers: [{ id: "identifier-1", scheme: "isbn_13", value: "978123", normalized_value: "hidden" }],
      catalog_tags: [{ id: "tag-1", name: "Fantasy", slug: "fantasy", normalized_name: "hidden" }],
      file: { format: "epub", file_size: 1536, checksum: "checksum", download_url: "http://127.0.0.1:8000/api/v1/library/books/book-1/download/?source=detail", storage_path: "hidden", source_filename: "hidden.epub" },
      groups: [{ id: "group-1", name: "Readers", description: "Visible", is_public_group: false, memberships: ["hidden"] }],
      source_filename: "hidden.epub", import_source: "hidden", book_file: "hidden/path.epub",
    };
    const client: ApiClient = { request: async <T>(path: string) => { calls.push(path); return wireBook as T; } };

    const book = await getBook("book/id", client);

    expect(calls).toEqual(["/api/v1/library/books/book%2Fid/"]);
    expect(book).toEqual({
      id: "book-1", title: "The Book", sortTitle: "Book, The", subtitle: "A subtitle",
      authors: [{ id: "author-1", name: "Ada Author" }],
      series: { id: "series-1", name: "A Series", sortName: "Series, A", seriesIndex: "2.00" },
      language: "en", publisher: "A Press", publishedYear: 2020, publishedMonth: 3, publishedDay: null,
      publishedDatePrecision: "month", coverUrl: "/media/cover.jpg", description: "Description",
      identifiers: [{ id: "identifier-1", scheme: "isbn_13", value: "978123" }],
      catalogTags: [{ id: "tag-1", name: "Fantasy", slug: "fantasy" }],
      file: { format: "epub", fileSize: 1536, checksum: "checksum", downloadUrl: "/api/v1/library/books/book-1/download/?source=detail" },
      groups: [{ id: "group-1", name: "Readers", description: "Visible", isPublicGroup: false }],
    });
    for (const field of ["sourceFilename", "importSource", "bookFile", "storagePath"]) expect(book).not.toHaveProperty(field);
    expect(book.authors[0]).not.toHaveProperty("normalizedName");
    expect(book.identifiers[0]).not.toHaveProperty("normalizedValue");
    expect(book.file).not.toHaveProperty("storagePath");
  });

  it("preserves null series/file projections and blank detail strings", async () => {
    const client: ApiClient = { request: async <T>() => ({
      id: "book", title: "Book", sort_title: "", subtitle: "", authors: [], series: null,
      language: "", publisher: "", published_year: null, published_month: null, published_day: null,
      published_date_precision: "", cover_url: null, description: "", identifiers: [], catalog_tags: [],
      file: null, groups: [],
    }) as T };
    await expect(getBook("book", client)).resolves.toMatchObject({
      sortTitle: "", subtitle: "", series: null, publishedYear: null, coverUrl: null,
      description: "", file: null,
    });
  });

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

  it("uses broad Library search with Shelf and Group candidate exclusions", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return { count: 1, next: null, previous: null, results: [compactWireBook] } as T;
    } };

    await expect(searchLibraryBooks({
      q: " Book ", excludeShelfId: "shelf/id", excludeGroupId: "group/id",
      ordering: "title", page: 2, pageSize: 30,
    }, client)).resolves.toMatchObject({ items: [{ id: "book-1", title: "The Book" }] });
    await searchLibraryBooks({ q: " Book ", excludeShelfId: "shelf/id" }, client);
    expect(calls).toEqual([
      "/api/v1/library/search?q=Book&exclude_shelf=shelf%2Fid&exclude_group=group%2Fid&ordering=title&page=2&page_size=30",
      "/api/v1/library/search?q=Book&exclude_shelf=shelf%2Fid",
    ]);
  });

  it("serializes selected Author and Series Book filters with the existing query controls", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return { count: 0, next: null, previous: null, results: [] } as T;
    } };
    await listBooks({ authorId: "author-id", tag: "fantasy", q: " Book ", ordering: "-title", page: 2, pageSize: 30 }, client);
    await listBooks({ seriesId: "series-id", tag: "history", q: " Saga ", ordering: "series_index", page: 3, pageSize: 40 }, client);
    expect(calls).toEqual([
      "/api/v1/library/books/?q=Book&tag=fantasy&author=author-id&ordering=-title&page=2&page_size=30",
      "/api/v1/library/books/?q=Saga&tag=history&series=series-id&ordering=series_index&page=3&page_size=40",
    ]);
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

  it("serializes Author and Series axis queries, including every supported ordering", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return { count: 0, next: null, previous: null, results: [] } as T;
    } };
    for (const ordering of ["name", "-name", "book_count", "-book_count"] as const) {
      await listAuthors({ q: " Ada ", tag: "history", ordering, includePreviewBooks: true, page: 2, pageSize: 30 }, client);
    }
    await listSeries({ q: " Saga ", tag: "fantasy", ordering: "-book_count", includePreviewBooks: true, page: 3, pageSize: 40 }, client);
    expect(calls).toEqual([
      ...["name", "-name", "book_count", "-book_count"].map((ordering) => `/api/v1/library/authors/?q=Ada&tag=history&ordering=${ordering}&include_preview_books=true&page=2&page_size=30`),
      "/api/v1/library/series/?q=Saga&tag=fantasy&ordering=-book_count&include_preview_books=true&page=3&page_size=40",
    ]);
  });

  it("maps axis summaries and keeps absent previews absent", async () => {
    const responses = [
      { id: "author-1", name: "Ada", sort_name: "Ada", biography: "Not for the row", book_count: 2, preview_books: [{ id: "book-1", title: "One", cover_url: null, extra: "hidden" }], normalized_name: "hidden" },
      { id: "series-1", name: "Saga", sort_name: "Saga", summary: "Not for the row", book_count: 1 },
    ];
    const client: ApiClient = { request: async <T>() => ({ count: 1, next: null, previous: null, results: [responses.shift()] }) as T };
    const author = (await listAuthors({}, client)).items[0]!;
    const series = (await listSeries({}, client)).items[0]!;
    expect(author).toEqual({ id: "author-1", name: "Ada", sortName: "Ada", biography: "Not for the row", bookCount: 2, previewBooks: [{ id: "book-1", title: "One", coverUrl: null }] });
    expect(author.previewBooks?.[0]).not.toHaveProperty("extra");
    expect(author).not.toHaveProperty("normalizedName");
    expect(series).toEqual({ id: "series-1", name: "Saga", sortName: "Saga", summary: "Not for the row", bookCount: 1 });
    expect(series).not.toHaveProperty("previewBooks");
  });
});

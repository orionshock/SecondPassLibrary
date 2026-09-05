export interface Page<T> {
  items: T[];
  count: number;
  next: string | null;
  previous: string | null;
}

export interface ApiPage<T> {
  results: T[];
  count: number;
  next: string | null;
  previous: string | null;
}

export function toPage<T, U>(page: ApiPage<T>, mapItem: (item: T) => U): Page<U> {
  return {
    items: page.results.map(mapItem),
    count: page.count,
    next: page.next,
    previous: page.previous,
  };
}

/** @internal Shared traversal for SDK helpers that intentionally read every page. */
export async function collectPaginatedResults<T, U>(
  firstPath: string,
  readPage: (path: string) => Promise<ApiPage<T>>,
  mapItem: (item: T) => U,
): Promise<U[]> {
  const items: U[] = [];
  let path: string | null = firstPath;
  while (path) {
    const page = await readPage(path);
    items.push(...page.results.map(mapItem));
    path = page.next ? paginationPath(page.next) : null;
  }
  return items;
}

function paginationPath(value: string): string {
  if (value.startsWith("/") && !value.startsWith("//")) return value;
  const url = new URL(value, "http://pagination.invalid");
  return `${url.pathname}${url.search}`;
}

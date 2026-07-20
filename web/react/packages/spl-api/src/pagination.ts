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

import { ApiError, type Page } from "@second-pass/spl-api";

export async function loadShelfPageWithRecovery<Item, Query extends { page?: number; pageSize?: number }>(
  query: Query,
  request: (query: Query) => Promise<Page<Item>>,
): Promise<{ page: Page<Item>; correctedPage: number }> {
  const requestedPage = query.page ?? 1;
  try {
    return { page: await request(query), correctedPage: requestedPage };
  } catch (error) {
    if (requestedPage <= 1 || !(error instanceof ApiError) || error.status !== 404) throw error;
    const firstPage = await request({ ...query, page: 1 });
    const maxPage = Math.max(1, Math.ceil(firstPage.count / (query.pageSize ?? 20)));
    if (maxPage === 1) return { page: firstPage, correctedPage: 1 };
    return { page: await request({ ...query, page: maxPage }), correctedPage: maxPage };
  }
}

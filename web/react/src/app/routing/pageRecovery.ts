import { ApiError } from "@second-pass/spl-api";

export interface PageRecoveryOptions<TPage extends { count: number }, TLocation> {
  requestedPage: number;
  pageSize: number;
  recoveryKey: string;
  recoveredKeys: Set<string>;
  fetchPage: (page: number) => Promise<TPage>;
  buildRecoveredLocation: (page: number) => TLocation;
  replaceLocation: (location: TLocation) => boolean | void;
}

export interface PageRecoveryResult<TPage> {
  page: TPage;
  correctedPage: number;
  recovered: boolean;
}

export async function loadPageWithRecovery<TPage extends { count: number }, TLocation>(
  options: PageRecoveryOptions<TPage, TLocation>,
): Promise<PageRecoveryResult<TPage>> {
  const {
    requestedPage,
    pageSize,
    recoveryKey,
    recoveredKeys,
    fetchPage,
    buildRecoveredLocation,
    replaceLocation,
  } = options;

  try {
    return { page: await fetchPage(requestedPage), correctedPage: requestedPage, recovered: false };
  } catch (error) {
    if (!isRecoverablePageError(error, requestedPage) || recoveredKeys.has(recoveryKey)) throw error;

    const firstPage = await fetchPage(1);
    const maxPage = Math.max(1, Math.ceil(firstPage.count / Math.max(1, pageSize)));
    const page = maxPage === 1 ? firstPage : await fetchPage(maxPage);
    if (replaceLocation(buildRecoveredLocation(maxPage)) !== false) recoveredKeys.add(recoveryKey);
    return { page, correctedPage: maxPage, recovered: true };
  }
}

function isRecoverablePageError(error: unknown, requestedPage: number): boolean {
  return requestedPage > 1 && error instanceof ApiError && error.status === 404;
}

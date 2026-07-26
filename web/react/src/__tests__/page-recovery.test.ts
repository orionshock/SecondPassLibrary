import { describe, expect, it, vi } from "vitest";

import { ApiError, type Page } from "@second-pass/spl-api";
import { loadPageWithRecovery } from "../app/routing/pageRecovery";

const page = (count: number): Page<never> => ({ items: [], count, next: null, previous: null });

function options(overrides: Partial<Parameters<typeof loadPageWithRecovery<Page<never>, string>>[0]> = {}) {
  return {
    requestedPage: 9,
    pageSize: 20,
    recoveryKey: "query",
    recoveredKeys: new Set<string>(),
    fetchPage: vi.fn(async (requestedPage: number) => {
      if (requestedPage === 9) throw new ApiError("Invalid page.", 404);
      return page(45);
    }),
    buildRecoveredLocation: (recoveredPage: number) => `/items?page=${recoveredPage}`,
    replaceLocation: vi.fn<(location: string) => void>(),
    ...overrides,
  };
}

describe("loadPageWithRecovery", () => {
  it("does not recover non-page errors", async () => {
    const setup = options({ fetchPage: async () => { throw new ApiError("Broken.", 500); } });
    await expect(loadPageWithRecovery(setup)).rejects.toThrow("Broken");
    expect(setup.replaceLocation).not.toHaveBeenCalled();
  });

  it("does not recover page-one errors", async () => {
    const setup = options({ requestedPage: 1, fetchPage: async () => { throw new ApiError("Not found.", 404); } });
    await expect(loadPageWithRecovery(setup)).rejects.toThrow("Not found");
    expect(setup.replaceLocation).not.toHaveBeenCalled();
  });

  it("probes page one, fetches the final page, and replaces with the caller-built location", async () => {
    const setup = options();
    const result = await loadPageWithRecovery(setup);
    expect(result).toMatchObject({ correctedPage: 3, recovered: true });
    expect(setup.fetchPage).toHaveBeenCalledTimes(3);
    expect(vi.mocked(setup.fetchPage).mock.calls.map(([requestedPage]) => requestedPage)).toEqual([9, 1, 3]);
    expect(setup.replaceLocation).toHaveBeenCalledWith("/items?page=3");
  });

  it("recovers an empty result to page one without fetching it twice", async () => {
    const setup = options({ fetchPage: vi.fn(async (requestedPage: number) => {
      if (requestedPage === 9) throw new ApiError("Invalid page.", 404);
      return page(0);
    }) });
    const result = await loadPageWithRecovery(setup);
    expect(result).toMatchObject({ correctedPage: 1, recovered: true });
    expect(setup.fetchPage).toHaveBeenCalledTimes(2);
  });

  it("does not recover the same query key twice", async () => {
    const recoveredKeys = new Set<string>();
    await loadPageWithRecovery(options({ recoveredKeys }));
    const repeated = options({ recoveredKeys });
    await expect(loadPageWithRecovery(repeated)).rejects.toThrow("Invalid page");
    expect(repeated.fetchPage).toHaveBeenCalledTimes(1);
    expect(repeated.replaceLocation).not.toHaveBeenCalled();
  });
});

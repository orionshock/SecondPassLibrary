/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, RouterProvider, useSearchParams } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, type Page } from "@second-pass/spl-api";
import { useUrlCollectionLifecycle } from "../../src/app/routing/useUrlCollectionLifecycle";
import { buttonNamed, deferred } from "../support/domInteraction";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const page = (label: string, count = 1): Page<string> => ({ items: [label], count, next: null, previous: null });
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

function Harness({ request }: { request: (query: string, page: number) => Promise<Page<string>> }) {
  const [searchParameters] = useSearchParams();
  const query = searchParameters.get("q") ?? "";
  const parsedPage = Number(searchParameters.get("page"));
  const requestedPage = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
  const canonical = new URLSearchParams();
  if (query) canonical.set("q", query);
  if (requestedPage > 1) canonical.set("page", String(requestedPage));
  const canonicalQuery = canonical.toString();
  const load = useUrlCollectionLifecycle({
    scope: "test",
    canonicalQuery,
    page: requestedPage,
    pageSize: 20,
    loadPage: (candidatePage) => request(query, candidatePage),
    queryForPage: (candidatePage) => {
      const recovered = new URLSearchParams(canonicalQuery);
      if (candidatePage > 1) recovered.set("page", String(candidatePage));
      else recovered.delete("page");
      return recovered.toString();
    },
  });
  return <>
    <output>{load.loading ? "loading" : load.error ? "error" : load.page?.items[0]}</output>
    <button type="button" onClick={load.reload}>Reload</button>
    <button type="button" onClick={load.retry}>Retry</button>
  </>;
}

async function mount(path: string, request: (query: string, page: number) => Promise<Page<string>>) {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const router = createMemoryRouter([{ path: "/items", element: <Harness request={request} /> }], { initialEntries: [path] });
  const locations: string[] = [];
  router.subscribe(({ location }) => locations.push(location.search));
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, locations, router };
}

describe("useUrlCollectionLifecycle", () => {
  it("replaces a noncanonical query once without losing valid query state", async () => {
    const request = vi.fn(async (query: string) => page(query));
    const { container, locations, router } = await mount("/items?page=invalid&q=kept", request);

    expect(router.state.location.search).toBe("?q=kept");
    expect(router.state.historyAction).toBe("REPLACE");
    expect(locations.filter((location) => location === "?q=kept")).toHaveLength(1);
    expect(request).toHaveBeenCalledOnce();
    expect(container.querySelector("output")?.textContent).toBe("kept");
  });

  it("never lets a stale response replace the active query result", async () => {
    const oldRequest = deferred<Page<string>>();
    const newRequest = deferred<Page<string>>();
    const request = vi.fn((query: string) => query === "old" ? oldRequest.promise : newRequest.promise);
    const { container, router } = await mount("/items?q=old", request);

    await act(async () => router.navigate("/items?q=new"));
    await act(async () => newRequest.resolve(page("new")));
    await act(async () => oldRequest.resolve(page("old")));

    expect(container.querySelector("output")?.textContent).toBe("new");
  });

  it("recovers an invalid page once and canonically replaces the URL", async () => {
    const request = vi.fn(async (_query: string, requestedPage: number) => {
      if (requestedPage === 9) throw new ApiError("Invalid page.", 404);
      return page(`page-${requestedPage}`, 45);
    });
    const { container, router } = await mount("/items?q=kept&page=9", request);

    expect(request.mock.calls.slice(0, 3).map(([, requestedPage]) => requestedPage)).toEqual([9, 1, 3]);
    expect(router.state.location.search).toBe("?q=kept&page=3");
    expect(container.querySelector("output")?.textContent).toBe("page-3");
  });

  it("does not enter another recovery cycle if the recovered destination fails", async () => {
    let finalPageRequests = 0;
    const request = vi.fn(async (_query: string, requestedPage: number) => {
      if (requestedPage === 9) throw new ApiError("Invalid page.", 404);
      if (requestedPage === 3 && ++finalPageRequests > 1) throw new ApiError("Invalid page.", 404);
      return page(`page-${requestedPage}`, 45);
    });
    const { container } = await mount("/items?page=9", request);

    expect(request.mock.calls.map(([, requestedPage]) => requestedPage)).toEqual([9, 1, 3, 3]);
    expect(container.querySelector("output")?.textContent).toBe("error");
  });

  it("starts a new generation on retry and ignores the prior completion", async () => {
    const first = deferred<Page<string>>();
    const second = deferred<Page<string>>();
    const request = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const { container } = await mount("/items?q=kept", request);

    await act(async () => buttonNamed(container, "Retry").click());
    await act(async () => second.resolve(page("retried")));
    await act(async () => first.resolve(page("stale")));

    expect(request).toHaveBeenCalledTimes(2);
    expect(request.mock.calls[1]?.[0]).toBe("kept");
    expect(container.querySelector("output")?.textContent).toBe("retried");
  });

  it("allows a changed collection to recover again when explicitly reloaded", async () => {
    let secondPageRequests = 0;
    const request = vi.fn(async (_query: string, requestedPage: number) => {
      if (requestedPage === 2 && ++secondPageRequests > 1) {
        throw new ApiError("Invalid page.", 404);
      }
      return page(`page-${requestedPage}`, requestedPage === 1 ? 20 : 21);
    });
    const { container, router } = await mount("/items?q=kept&page=2", request);

    await act(async () => buttonNamed(container, "Reload").click());

    expect(request.mock.calls.map(([, requestedPage]) => requestedPage)).toEqual([2, 2, 1, 1]);
    expect(router.state.location.search).toBe("?q=kept");
    expect(router.state.historyAction).toBe("REPLACE");
    expect(container.querySelector("output")?.textContent).toBe("page-1");
  });
});

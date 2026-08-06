import { describe, expect, it } from "vitest";

import {
  shelfDetailPath,
  shelfDetailSearchParams,
  shelfDetailStateFromSearchParams,
  shelfEditPathWithState,
  shelfEditSearchParams,
  shelfEditStateDuringItemMutation,
  shelfEditStateFromSearchParams,
  shelfItemsSdkQuery,
  shelvesListPath,
  shelvesListSdkQuery,
  shelvesListSearchParams,
  shelvesListStateFromSearchParams,
  withShelfDetailChange,
  withShelfEditPage,
  withShelfEditTab,
  withShelvesListChange,
} from "../features/shelves/shelvesQuery";

describe("Shelves URL state", () => {
  it("uses Personal defaults and canonical list query ordering", () => {
    const defaults = shelvesListStateFromSearchParams(new URLSearchParams());
    expect(shelvesListPath(defaults)).toBe("/shelves");
    expect(shelvesListSdkQuery(defaults)).toEqual({
      scope: "personal", ordering: "name", includePreviewBooks: true,
      previewLimit: 12, page: 1, pageSize: 20,
    });

    const state = shelvesListStateFromSearchParams(new URLSearchParams(
      "page_size=40&page=3&ordering=-item_count&scope=group",
    ));
    expect(shelvesListSearchParams(state).toString()).toBe("scope=group&ordering=-item_count&page=3&page_size=40");
    expect(shelvesListPath(state)).toBe("/shelves?scope=group&ordering=-item_count&page=3&page_size=40");
    expect(shelvesListSdkQuery(state)).toEqual({
      scope: "group", ordering: "-item_count", includePreviewBooks: true,
      previewLimit: 12, page: 3, pageSize: 40,
    });
    expect(shelvesListStateFromSearchParams(new URLSearchParams("ordering=-name")).ordering).toBe("-name");
    expect(shelvesListStateFromSearchParams(new URLSearchParams("ordering=item_count")).ordering).toBe("item_count");
    expect(shelvesListStateFromSearchParams(new URLSearchParams("scope=all&ordering=bad&page=0&page_size=99"))).toEqual(defaults);
  });

  it("serializes supported scopes and resets list pages only for filter changes", () => {
    const current = shelvesListStateFromSearchParams(new URLSearchParams("scope=shared&page=4&page_size=40"));
    expect(shelvesListPath(current)).toBe("/shelves?scope=shared&page=4&page_size=40");
    expect(withShelvesListChange(current, { scope: "group" }).page).toBe(1);
    expect(withShelvesListChange(current, { ordering: "-item_count" }).page).toBe(1);
    expect(withShelvesListChange(current, { pageSize: 30 }).page).toBe(1);
    expect(withShelvesListChange(current, { page: 2 }, false).page).toBe(2);
  });

  it("normalizes Shelf detail ordering and omits defaults", () => {
    const defaults = shelfDetailStateFromSearchParams(new URLSearchParams());
    expect(shelfDetailPath("shelf/id", defaults)).toBe("/shelves/shelf%2Fid");
    expect(shelfItemsSdkQuery(defaults)).toEqual({ ordering: "position", page: 1, pageSize: 20 });

    const state = shelfDetailStateFromSearchParams(new URLSearchParams("page_size=30&page=2&ordering=author"));
    expect(shelfDetailSearchParams(state).toString()).toBe("ordering=author&page=2&page_size=30");
    expect(shelfDetailPath("shelf/id", state)).toBe("/shelves/shelf%2Fid?ordering=author&page=2&page_size=30");
    for (const ordering of ["-position", "-title", "-author"] as const) {
      const reverse = shelfDetailStateFromSearchParams(new URLSearchParams(`ordering=${ordering}`));
      expect(reverse.ordering).toBe(ordering);
      expect(shelfDetailSearchParams(reverse).toString()).toBe(`ordering=${ordering}`);
      expect(shelfItemsSdkQuery(reverse).ordering).toBe(ordering);
    }
    expect(withShelfDetailChange(state, { ordering: "title" }).page).toBe(1);
    expect(withShelfDetailChange(state, { pageSize: 40 }).page).toBe(1);
    expect(withShelfDetailChange(state, { page: 4 }, false).page).toBe(4);
    expect(shelfDetailStateFromSearchParams(new URLSearchParams("ordering=bad&page=-1&page_size=10"))).toEqual(defaults);
  });

  it("keeps Shelf Edit Details canonical and normalizes item-tab URL state", () => {
    const details = shelfEditStateFromSearchParams(new URLSearchParams("tab=bad&q=ignored&page=4&page_size=40"));
    expect(details).toEqual({ tab: "details", page: 1, pageSize: 20, q: "" });
    expect(shelfEditPathWithState("shelf/id", details)).toBe("/shelves/shelf%2Fid/edit");

    const addBooks = shelfEditStateFromSearchParams(new URLSearchParams("q= Storm &page_size=30&page=2&tab=add-books"));
    expect(shelfEditSearchParams(addBooks).toString()).toBe("tab=add-books&page=2&page_size=30&q=Storm");
    expect(shelfEditPathWithState("shelf/id", addBooks)).toBe(
      "/shelves/shelf%2Fid/edit?tab=add-books&page=2&page_size=30&q=Storm",
    );
    expect(withShelfEditTab(addBooks, "books")).toEqual({ tab: "books", page: 1, pageSize: 30, q: "" });
    expect(withShelfEditPage(addBooks, { pageSize: 40 })).toMatchObject({ page: 1, pageSize: 40 });

    const requestedDuringMutation = shelfEditStateFromSearchParams(new URLSearchParams("tab=details"));
    expect(shelfEditStateDuringItemMutation(requestedDuringMutation, addBooks, true)).toBe(addBooks);
    expect(shelfEditStateDuringItemMutation(requestedDuringMutation, addBooks, false)).toBe(requestedDuringMutation);
  });
});

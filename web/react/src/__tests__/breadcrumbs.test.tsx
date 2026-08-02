import { renderToStaticMarkup } from "react-dom/server";
import { createMemoryRouter, MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { BreadcrumbsComponent } from "../app/navigation/BreadcrumbsComponent";
import {
  appendBreadcrumbTrail,
  breadcrumbLinkState,
  breadcrumbNavigationState,
  readIncomingBreadcrumbTrail,
  resolveBreadcrumbTrail,
  type BreadcrumbItem,
} from "../app/navigation/breadcrumbs";
import {
  clientPairingBreadcrumbFallback,
  passwordBreadcrumbFallback,
  profileBreadcrumbFallback,
} from "../app/navigation/accountBreadcrumbs";

function breadcrumbText(items: readonly BreadcrumbItem[]): string {
  return items.map(({ label }) => label).join("");
}

function renderBreadcrumbs(items: readonly BreadcrumbItem[]): string {
  return renderToStaticMarkup(<MemoryRouter><BreadcrumbsComponent items={items} /></MemoryRouter>);
}

describe("contextual breadcrumbs", () => {
  it("renders linked ancestors and a non-linked current item with CSS-only separators", () => {
    const markup = renderBreadcrumbs(passwordBreadcrumbFallback);
    expect(markup).toContain('href="/profile"');
    expect(markup).toContain("Profile");
    expect(markup).toContain('aria-current="page"');
    expect(markup).toContain("Password");
    expect(breadcrumbText(passwordBreadcrumbFallback)).toBe("ProfilePassword");
  });

  it("renders validated semantic icons decoratively and leaves text-only items icon-free", () => {
    const withIcon = renderBreadcrumbs([{ label: "Library", icon: "library" }]);
    const withoutIcon = renderBreadcrumbs([{ label: "Edit" }]);
    expect(withIcon).toContain("local_library");
    expect(withIcon).toContain('aria-hidden="true"');
    expect(withIcon).toContain("Library");
    expect(withoutIcon).not.toContain("material-symbols-outlined");
    expect(withoutIcon).toContain("Edit");
  });

  it("suppresses breadcrumbs on the base Profile route and provides child fallbacks", () => {
    expect(resolveBreadcrumbTrail(undefined, profileBreadcrumbFallback)).toEqual([]);
    expect(breadcrumbText(resolveBreadcrumbTrail(undefined, profileBreadcrumbFallback))).toBe("");
    expect(breadcrumbText(resolveBreadcrumbTrail(undefined, passwordBreadcrumbFallback))).toBe("ProfilePassword");
    expect(breadcrumbText(resolveBreadcrumbTrail(undefined, clientPairingBreadcrumbFallback))).toBe("ProfileClient pairing");
  });

  it("honors a valid incoming contextual trail", () => {
    const contextual = appendBreadcrumbTrail(
      [{ label: "Groups", to: "/groups" }, { label: "Book Club", to: "/groups/book-club" }],
      { label: "Edit" },
    );
    const state = breadcrumbNavigationState(contextual);
    expect(resolveBreadcrumbTrail(state, passwordBreadcrumbFallback)).toEqual(contextual);
  });

  it("bounds extended deep trails without discarding the root or newest context", () => {
    const parent = [
      { label: "Library", to: "/library" },
      ...Array.from({ length: 11 }, (_, index) => ({ label: `Context ${index + 1}` })),
    ];
    const trail = appendBreadcrumbTrail(parent, { label: "Selected Book", icon: "book" });

    expect(trail).toHaveLength(12);
    expect(trail[0]).toEqual({ label: "Library", to: "/library" });
    expect(trail.at(-1)).toEqual({ label: "Selected Book", icon: "book" });
    expect(resolveBreadcrumbTrail(breadcrumbNavigationState(trail), [])).toEqual(trail);
  });

  it("preserves breadcrumb context by default and resets only explicit branch links", () => {
    const trail: BreadcrumbItem[] = [
      { label: "Library", to: "/library", resetTrail: true, icon: "library" },
      { label: "Dresden Files", to: "/library?view=series&series=id", icon: "series" },
      { label: "Storm Front", to: "/library/books/id", icon: "book" },
      { label: "Edit" },
    ];
    expect(breadcrumbLinkState(trail, 0)).toBeUndefined();
    expect(resolveBreadcrumbTrail(breadcrumbLinkState(trail, 2), [])).toEqual([
      { label: "Library", to: "/library", icon: "library" },
      { label: "Dresden Files", to: "/library?view=series&series=id", icon: "series" },
      { label: "Storm Front", to: "/library/books/id", icon: "book" },
    ]);
  });

  it("rejects location state containing an unknown semantic icon", () => {
    const state = breadcrumbNavigationState([{ label: "Library", icon: "library" }]);
    state.breadcrumbTrail[0] = { label: "Library", icon: "raw_material_token" as "library" };
    expect(readIncomingBreadcrumbTrail(state)).toBeUndefined();
    expect(resolveBreadcrumbTrail(state, passwordBreadcrumbFallback)).toEqual(passwordBreadcrumbFallback);
  });

  it("falls back when incoming location state is malformed", () => {
    expect(readIncomingBreadcrumbTrail({ breadcrumbTrail: [{ label: "Unsafe", to: "https://example.test" }] })).toBeUndefined();
    expect(resolveBreadcrumbTrail({ breadcrumbTrail: [{ label: "" }] }, passwordBreadcrumbFallback)).toEqual(passwordBreadcrumbFallback);
  });

  it("does not replay breadcrumb state from an earlier app runtime", () => {
    const staleState = { ...breadcrumbNavigationState(passwordBreadcrumbFallback), breadcrumbContextId: "previous-runtime" };
    expect(resolveBreadcrumbTrail(staleState, profileBreadcrumbFallback)).toEqual(profileBreadcrumbFallback);
  });

  it("suppresses the forced password trail", () => {
    expect(resolveBreadcrumbTrail(breadcrumbNavigationState(passwordBreadcrumbFallback), passwordBreadcrumbFallback, true)).toEqual([]);
    expect(renderBreadcrumbs([])).toBe("");
  });

  it("drops stale context when navigation starts a new top-level branch", async () => {
    const router = createMemoryRouter([{ path: "*", element: null }], {
      initialEntries: [{ pathname: "/profile/password", state: breadcrumbNavigationState(passwordBreadcrumbFallback) }],
    });
    await router.navigate("/library");
    expect(router.state.location.state).toBeNull();
    expect(resolveBreadcrumbTrail(router.state.location.state, [{ label: "Library" }])).toEqual([{ label: "Library" }]);
  });
});

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
  return renderBreadcrumbs(items).replace(/<[^>]+>/g, "");
}

function renderBreadcrumbs(items: readonly BreadcrumbItem[]): string {
  return renderToStaticMarkup(<MemoryRouter><BreadcrumbsComponent items={items} /></MemoryRouter>);
}

describe("contextual breadcrumbs", () => {
  it("renders linked ancestors and a non-linked current item with CSS-only separators", () => {
    const markup = renderBreadcrumbs(passwordBreadcrumbFallback);
    expect(markup).toMatch(/<a href="\/profile"[^>]*>Profile<\/a>/);
    expect(markup).toContain('<span aria-current="page">Password</span>');
    expect(breadcrumbText(passwordBreadcrumbFallback)).toBe("ProfilePassword");
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

  it("preserves breadcrumb context by default and resets only explicit branch links", () => {
    const trail: BreadcrumbItem[] = [
      { label: "Library", to: "/library", resetTrail: true },
      { label: "Dresden Files", to: "/library?view=series&series=id" },
      { label: "Storm Front", to: "/library/books/id" },
      { label: "Edit" },
    ];
    expect(breadcrumbLinkState(trail, 0)).toBeUndefined();
    expect(resolveBreadcrumbTrail(breadcrumbLinkState(trail, 2), [])).toEqual([
      { label: "Library", to: "/library" },
      { label: "Dresden Files", to: "/library?view=series&series=id" },
      { label: "Storm Front", to: "/library/books/id" },
    ]);
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

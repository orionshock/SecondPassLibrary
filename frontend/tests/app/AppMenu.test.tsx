import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import {
  AppMenuComponent,
  AppMenuItemsComponent,
  appMenuReducer,
  menuIndexForKey,
  menuTriggerOpensForKey,
  type AppMenuItem,
} from "../../src/app/layout/AppMenuComponent";
import { accountMenuItems } from "../../src/app/layout/AppOrchestrator";

const accountItems: readonly AppMenuItem[] = accountMenuItems("/profile/password");

describe("app-shell menus", () => {
  it("renders an explicit username-and-chevron account trigger without a person icon", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><AppMenuComponent
      className="account-menu"
      trigger={<><span>owner</span><span className="material-icon">expand_more</span></>}
      triggerLabel="Open account menu for owner"
      menuLabel="Account menu for owner"
      items={accountItems}
    /></MemoryRouter>);

    expect(markup).toContain("owner");
    expect(markup).toContain("expand_more");
    expect(markup).not.toContain(">person<");
    expect(markup).toContain('aria-haspopup="menu"');
    expect(markup).toContain('aria-expanded="false"');
  });

  it("renders Profile settings and an accessible POST logout action with icons", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><AppMenuItemsComponent
      label="Account menu for owner"
      items={accountItems}
      onSelect={vi.fn()}
    /></MemoryRouter>);

    expect(markup).toContain('role="menu"');
    expect(markup).toContain('href="/profile"');
    expect(markup).toContain("Profile settings");
    expect(markup).toContain(">person<");
    expect(markup).not.toContain('href="/logout/"');
    expect(markup).toMatch(/<button[^>]*type="button"[^>]*>.*Log out/s);
    expect(markup).toContain("Log out");
    expect(markup).toContain(">logout<");
    expect(markup).toMatch(/aria-current="page"[^>]*href="\/profile"/);
  });

  it("closes on selection and invokes an action once", () => {
    const close = vi.fn();
    const action = vi.fn();
    const menu = AppMenuItemsComponent({
      label: "Actions",
      items: [{ key: "action", label: "Action", icon: "check", onSelect: action }],
      onSelect: close,
    }) as ReactElement<{ children: ReactElement<{ onClick: () => void }>[] }>;

    menu.props.children[0]!.props.onClick();
    expect(close).toHaveBeenCalledOnce();
    expect(action).toHaveBeenCalledOnce();
  });

  it("supports keyboard opening, cycling, Escape close, and focus endpoints", () => {
    expect(menuTriggerOpensForKey("ArrowDown")).toBe(true);
    expect(menuTriggerOpensForKey("Enter")).toBe(true);
    expect(menuTriggerOpensForKey(" ")).toBe(true);
    expect(menuTriggerOpensForKey("Escape")).toBe(false);
    expect(appMenuReducer(false, "open")).toBe(true);
    expect(appMenuReducer(true, "close")).toBe(false);
    expect(menuIndexForKey(0, 3, "ArrowDown")).toBe(1);
    expect(menuIndexForKey(0, 3, "ArrowUp")).toBe(2);
    expect(menuIndexForKey(1, 3, "Home")).toBe(0);
    expect(menuIndexForKey(1, 3, "End")).toBe(2);
  });

  it("renders active overflow items once with useful icon and text", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><AppMenuItemsComponent
      label="More navigation"
      items={[{ key: "imports", label: "Book Import", icon: "upload_file", to: "/imports", active: true }]}
      onSelect={vi.fn()}
    /></MemoryRouter>);

    expect((markup.match(/Book Import/g) ?? [])).toHaveLength(1);
    expect(markup).toContain(">upload_file<");
    expect(markup).toContain('aria-current="page"');
  });
});


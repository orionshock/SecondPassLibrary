/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AppMenuComponent,
  AppMenuItemsComponent,
  type AppMenuItem,
} from "../../src/app/layout/AppMenuComponent";
import { accountMenuItems } from "../../src/app/layout/AppOrchestrator";

const accountItems: readonly AppMenuItem[] = accountMenuItems("/profile/password");

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
});

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

  it("closes after a mounted selection and invokes the action once", async () => {
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    const action = vi.fn();
    await act(async () => root?.render(<MemoryRouter><AppMenuComponent
      trigger={<span>Actions</span>}
      triggerLabel="Open actions"
      menuLabel="Actions"
      items={[{ key: "action", label: "Action", icon: "check", onSelect: action }]}
    /></MemoryRouter>));

    const trigger = container.querySelector<HTMLButtonElement>('[aria-haspopup="menu"]')!;
    await act(async () => trigger.click());
    const item = container.querySelector<HTMLButtonElement>('[role="menuitem"]')!;
    expect(document.activeElement).toBe(item);
    await act(async () => item.click());
    expect(action).toHaveBeenCalledOnce();
    expect(container.querySelector('[role="menu"]')).toBeNull();
  });

  it.each(["Enter", " "])("opens from the %s key through the rendered trigger", async (key) => {
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => root?.render(<MemoryRouter><AppMenuComponent
      trigger={<span>Actions</span>}
      triggerLabel="Open actions"
      menuLabel="Actions"
      items={[{ key: "action", label: "Action", icon: "check", onSelect: vi.fn() }]}
    /></MemoryRouter>));

    const trigger = container.querySelector<HTMLButtonElement>('[aria-haspopup="menu"]')!;
    await act(async () => trigger.dispatchEvent(
      new KeyboardEvent("keydown", { key, bubbles: true }),
    ));

    expect(container.querySelector('[role="menu"]')).not.toBeNull();
    expect(document.activeElement).toBe(container.querySelector('[role="menuitem"]'));
  });

  it("supports mounted keyboard opening, cycling, Escape close, and focus restoration", async () => {
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => root?.render(<MemoryRouter><AppMenuComponent
      trigger={<span>Actions</span>}
      triggerLabel="Open actions"
      menuLabel="Actions"
      items={[
        { key: "first", label: "First", icon: "looks_one", onSelect: vi.fn() },
        { key: "second", label: "Second", icon: "looks_two", onSelect: vi.fn() },
        { key: "third", label: "Third", icon: "looks_3", onSelect: vi.fn() },
      ]}
    /></MemoryRouter>));

    const trigger = container.querySelector<HTMLButtonElement>('[aria-haspopup="menu"]')!;
    trigger.focus();
    await act(async () => trigger.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true })));
    const items = container.querySelectorAll<HTMLElement>('[role="menuitem"]');
    expect(document.activeElement).toBe(items[0]);
    for (const [key, expected] of [
      ["ArrowDown", items[1]],
      ["End", items[2]],
      ["Home", items[0]],
      ["ArrowUp", items[2]],
    ] as const) {
      await act(async () => (document.activeElement as HTMLElement).dispatchEvent(
        new KeyboardEvent("keydown", { key, bubbles: true }),
      ));
      expect(document.activeElement).toBe(expected);
    }
    await act(async () => items[2]!.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
    expect(container.querySelector('[role="menu"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
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


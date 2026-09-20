/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";
import { AppBootstrapView } from "../../src/app/App";
import { passwordResumeDestination } from "../../src/app/router";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
});

const user = { username: "reader", mustChangePassword: true, isReader: true } as CurrentUser;
const server = { name: "Library", advancedLibraryGroupsEnabled: false } as ServerInfo;

function PasswordDestination() {
  const location = useLocation();
  return <div data-testid="password-resume">{String(location.state?.passwordResumeTo)}</div>;
}

describe("forced password resume routing", () => {
  it("gates a deep link and captures its pathname, query, and hash", async () => {
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    const router = createMemoryRouter([{
      path: "/",
      element: <AppBootstrapView state={{ status: "ready", user, server }} loginPath="/login/" onRetry={vi.fn()} onCurrentUserChange={vi.fn()} />,
      children: [
        { path: "library/books/:bookId", element: <div data-testid="book">Book</div> },
        { path: "profile/password", element: <PasswordDestination /> },
      ],
    }], { initialEntries: ["/library/books/book-1?view=notes#entry-2"] });

    await act(async () => root?.render(<RouterProvider router={router} />));

    expect(router.state.location.pathname).toBe("/profile/password");
    expect(container.querySelector('[data-testid="password-resume"]')?.textContent).toBe("/library/books/book-1?view=notes#entry-2");
    expect(container.querySelector('[data-testid="book"]')).toBeNull();
  });

  it("accepts only known internal Product UI routes", () => {
    expect(passwordResumeDestination("/library/books/book-1?view=notes#entry-2")).toBe("/library/books/book-1?view=notes#entry-2");
    for (const unsafe of [undefined, "https://elsewhere.example", "//elsewhere.example/path", "/\\elsewhere.example", "/library/%zz", "/library/%E0%A4%A", "/login/", "/setup/", "/logout/", "/profile/password", "/profile/password?again=1", "/missing"]) {
      expect(passwordResumeDestination(unsafe)).toBe("/");
    }
  });
});

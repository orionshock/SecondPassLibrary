/** @vitest-environment happy-dom */

import { act, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { normalizeMutationError } from "../../../src/shared/feedback/mutationState";
import { useFormSaveLifecycle } from "../../../src/shared/forms/useFormSaveLifecycle";
import { deferred, setControlValue, submit } from "../../support/domInteraction";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function LifecycleHarness({ save }: { save: (draft: string) => Promise<string> }) {
  const lifecycle = useFormSaveLifecycle({
    initialDraft: "",
    draftsEqual: (draft, baseline) => draft === baseline,
    discardMessage: "Discard changes?",
  });

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lifecycle.beginSave()) return;
    try {
      lifecycle.saveSucceeded(await save(lifecycle.draft), "Saved.");
    } catch (error: unknown) {
      lifecycle.saveFailed(normalizeMutationError(error));
    }
  }

  return <form data-dirty={lifecycle.dirty} aria-busy={lifecycle.mutation.pending} onSubmit={(event) => void onSubmit(event)}>
    <input
      aria-label="Draft"
      value={lifecycle.draft}
      disabled={lifecycle.mutation.pending}
      onChange={(event) => lifecycle.changeDraft(event.target.value)}
    />
    <button type="submit" disabled={lifecycle.mutation.pending}>Save</button>
    {lifecycle.mutation.error ? <p role="alert">{lifecycle.mutation.error.message}</p> : null}
  </form>;
}

describe("useFormSaveLifecycle", () => {
  it("owns pending, draft preservation, duplicate prevention, and navigation blocking", async () => {
    const first = deferred<string>();
    const save = vi.fn()
      .mockReturnValueOnce(first.promise)
      .mockResolvedValueOnce("Authoritative draft");
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    const router = createMemoryRouter([
      { path: "/edit", element: <LifecycleHarness save={save} /> },
      { path: "/away", element: <div data-testid="away" /> },
    ], { initialEntries: ["/edit"] });
    await act(async () => root?.render(<RouterProvider router={router} />));

    const input = container.querySelector<HTMLInputElement>('[aria-label="Draft"]')!;
    const form = container.querySelector<HTMLFormElement>("form")!;
    await act(async () => setControlValue(input, "Submitted draft"));
    expect(form.dataset.dirty).toBe("true");
    const unload = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(unload);
    expect(unload.defaultPrevented).toBe(true);

    act(() => submit(form));
    expect(input.disabled).toBe(true);
    await act(async () => setControlValue(input, "Newer draft"));
    expect(input.value).toBe("Submitted draft");
    act(() => submit(form));
    expect(save).toHaveBeenCalledOnce();
    await act(async () => router.navigate("/away"));
    expect(router.state.location.pathname).toBe("/edit");
    expect(confirm).not.toHaveBeenCalled();

    await act(async () => first.reject(new Error("Save failed.")));
    expect(input.disabled).toBe(false);
    expect(input.value).toBe("Submitted draft");
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
    await act(async () => router.navigate("/away"));
    expect(confirm).toHaveBeenCalledWith("Discard changes?");
    expect(router.state.location.pathname).toBe("/edit");

    await act(async () => submit(form));
    expect(input.value).toBe("Authoritative draft");
    expect(form.dataset.dirty).toBe("false");
    await act(async () => router.navigate("/away"));
    expect(router.state.location.pathname).toBe("/away");
  });
});

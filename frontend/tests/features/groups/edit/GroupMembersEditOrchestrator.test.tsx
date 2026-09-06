/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { GroupMembership, LibraryGroup } from "@second-pass/spl-api";
import { GroupMembersEditOrchestrator } from "../../../../src/features/groups/edit/GroupMembersEditOrchestrator";
import { buttonNamed, deferred, setControlValue, submit } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({
  listMembers: vi.fn(), listChoices: vi.fn(), addMember: vi.fn(), updateMember: vi.fn(), removeMember: vi.fn(),
}));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  listGroupMembers: sdk.listMembers,
  listUserChoices: sdk.listChoices,
  addGroupMember: sdk.addMember,
  updateGroupMember: sdk.updateMember,
  removeGroupMember: sdk.removeMember,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const group: LibraryGroup = { id: "group/id", name: "Readers", description: "", isPublicGroup: false };
const member: GroupMembership = { user: { profileId: "member-id", username: "reader" }, isCurator: false };
const page = (items: GroupMembership[]) => ({ items, count: items.length, next: null, previous: null });
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

async function mount(onPending = vi.fn()) {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  await act(async () => root?.render(<MemoryRouter><GroupMembersEditOrchestrator
    group={group}
    metadataPending={false}
    onMutationPendingChange={onPending}
  /></MemoryRouter>));
  return container;
}

describe("GroupMembersEditOrchestrator", () => {
  it("loads members, updates curator state, locks conflicting actions, and refreshes authority", async () => {
    sdk.listMembers.mockResolvedValueOnce(page([member])).mockResolvedValueOnce(page([{ ...member, isCurator: true }]));
    sdk.listChoices.mockResolvedValue({ items: [], count: 0, next: null, previous: null });
    const pending = deferred<GroupMembership>();
    sdk.updateMember.mockReturnValue(pending.promise);
    const onPending = vi.fn();
    const container = await mount(onPending);

    expect(sdk.listMembers).toHaveBeenCalledWith("group/id", { page: 1, pageSize: 20 });
    act(() => buttonNamed(container, "Make curator").click());
    expect(sdk.updateMember).toHaveBeenCalledWith("group/id", "member-id", { isCurator: true });
    expect(buttonNamed(container, "Remove reader from group").disabled).toBe(true);
    expect(onPending).toHaveBeenLastCalledWith(true);

    await act(async () => pending.resolve({ ...member, isCurator: true }));
    expect(sdk.listMembers).toHaveBeenCalledTimes(2);
    expect(buttonNamed(container, "Remove curator")).not.toBeNull();
  });

  it("adds a searched user and refreshes both authoritative lists", async () => {
    sdk.listMembers.mockResolvedValueOnce(page([member])).mockResolvedValueOnce(page([member, {
      user: { profileId: "new-id", username: "new-reader" }, isCurator: false,
    }]));
    sdk.listChoices
      .mockResolvedValueOnce({ items: [{ profileId: "new-id", username: "new-reader" }], count: 1, next: null, previous: null })
      .mockResolvedValueOnce({ items: [], count: 0, next: null, previous: null });
    sdk.addMember.mockResolvedValue(undefined);
    const container = await mount();

    await act(async () => setControlValue(container.querySelector<HTMLInputElement>("#group-add-members-search")!, "new"));
    await act(async () => submit(container.querySelector<HTMLFormElement>('form[role="search"]')!));
    await act(async () => buttonNamed(container, "Add").click());

    expect(sdk.addMember).toHaveBeenCalledWith("group/id", { userId: "new-id", isCurator: false });
    expect(sdk.listMembers).toHaveBeenCalledTimes(2);
    expect(sdk.listChoices).toHaveBeenCalledTimes(2);
    expect(container.textContent).toContain("new-reader");
  });

  it("keeps a member visible when confirmed removal fails", async () => {
    sdk.listMembers.mockResolvedValue(page([member]));
    sdk.removeMember.mockRejectedValue(new Error("Membership mutation failed."));
    vi.stubGlobal("confirm", vi.fn(() => true));
    const container = await mount();

    await act(async () => buttonNamed(container, "Remove reader from group").click());

    expect(sdk.removeMember).toHaveBeenCalledWith("group/id", "member-id");
    expect(container.textContent).toContain("reader");
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
  });

  it("removes a confirmed member and refreshes the authoritative list", async () => {
    sdk.listMembers.mockResolvedValueOnce(page([member])).mockResolvedValueOnce(page([]));
    sdk.removeMember.mockResolvedValue(undefined);
    vi.stubGlobal("confirm", vi.fn(() => true));
    const container = await mount();

    await act(async () => buttonNamed(container, "Remove reader from group").click());

    expect(sdk.removeMember).toHaveBeenCalledWith("group/id", "member-id");
    expect(sdk.listMembers).toHaveBeenCalledTimes(2);
    expect(container.querySelector('[aria-label="Remove reader from group"]')).toBeNull();
  });

  it("does not mutate membership when destructive confirmation is declined", async () => {
    sdk.listMembers.mockResolvedValue(page([member]));
    vi.stubGlobal("confirm", vi.fn(() => false));
    const container = await mount();

    await act(async () => buttonNamed(container, "Remove reader from group").click());

    expect(sdk.removeMember).not.toHaveBeenCalled();
    expect(container.textContent).toContain("reader");
  });
});

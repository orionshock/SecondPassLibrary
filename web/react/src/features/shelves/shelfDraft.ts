import type {
  CreateShelfInput,
  ShelfSummary,
  ShelfVisibility,
  UpdateShelfInput,
} from "@second-pass/spl-api";

import { LocalValidationError } from "../../shared/feedback/mutationState";

export interface ShelfDraft {
  name: string;
  description: string;
  ownerType: "user" | "group";
  ownerGroupId: string;
  visibility: ShelfVisibility;
}

export const emptyShelfDraft: ShelfDraft = {
  name: "",
  description: "",
  ownerType: "user",
  ownerGroupId: "",
  visibility: "private",
};

export function shelfDraftForGroupOwner(groupId: string): ShelfDraft {
  return { ...emptyShelfDraft, ownerType: "group", ownerGroupId: groupId };
}

export function shelfDraftFromSummary(shelf: ShelfSummary): ShelfDraft {
  return {
    name: shelf.name,
    description: shelf.description,
    ownerType: shelf.ownerType,
    ownerGroupId: shelf.ownerGroup?.id ?? "",
    visibility: shelf.ownerType === "group" ? "private" : shelf.visibility,
  };
}

export function validateShelfDraft(
  draft: ShelfDraft,
  manageableGroupIds?: readonly string[],
): void {
  const fields: Record<string, string[]> = {};
  const name = draft.name.trim();
  if (!name) fields.name = ["Name is required."];
  else if (name.length > 255) fields.name = ["Name must be 255 characters or fewer."];
  if (draft.ownerType !== "user" && draft.ownerType !== "group") {
    fields.ownerType = ["Owner is invalid."];
  }
  if (!(["private", "listed"] as const).includes(draft.visibility)) {
    fields.visibility = ["Visibility is invalid."];
  }
  if (draft.ownerType === "group" && !draft.ownerGroupId) {
    fields.ownerGroupId = ["Choose an owning group."];
  } else if (
    draft.ownerType === "group"
    && manageableGroupIds
    && !manageableGroupIds.includes(draft.ownerGroupId)
  ) {
    fields.ownerGroupId = ["Choose an available owning group."];
  }
  if (draft.ownerType === "user" && draft.ownerGroupId) {
    fields.ownerGroupId = ["Personal shelves cannot have an owning group."];
  }
  if (Object.keys(fields).length) {
    throw new LocalValidationError("Check the highlighted fields.", fields);
  }
}

export function createShelfInputFromDraft(draft: ShelfDraft): CreateShelfInput {
  return {
    name: draft.name.trim(),
    description: draft.description,
    ownerType: draft.ownerType,
    ...(draft.ownerType === "group" ? { ownerGroupId: draft.ownerGroupId } : {}),
    visibility: draft.ownerType === "group" ? "private" : draft.visibility,
  };
}

export function updateShelfInputFromDraft(draft: ShelfDraft): UpdateShelfInput {
  return {
    name: draft.name.trim(),
    description: draft.description,
    ...(draft.ownerType === "user" ? { visibility: draft.visibility } : {}),
  };
}

export function shelfDraftsEqual(left: ShelfDraft, right: ShelfDraft): boolean {
  return left.name.trim() === right.name.trim()
    && left.description === right.description
    && left.ownerType === right.ownerType
    && left.ownerGroupId === right.ownerGroupId
    && left.visibility === right.visibility;
}

export function withShelfOwnerType(
  draft: ShelfDraft,
  ownerType: ShelfDraft["ownerType"],
): ShelfDraft {
  return ownerType === "user"
    ? { ...draft, ownerType, ownerGroupId: "" }
    : { ...draft, ownerType, visibility: "private" };
}

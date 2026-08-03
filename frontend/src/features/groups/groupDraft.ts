import type {
  CreateGroupInput,
  LibraryGroup,
  UpdateGroupInput,
} from "@second-pass/spl-api";

import { LocalValidationError } from "../../shared/feedback/mutationState";

export interface GroupDraft {
  name: string;
  description: string;
}

export const emptyGroupDraft: GroupDraft = { name: "", description: "" };

export function groupDraftFromGroup(group: LibraryGroup): GroupDraft {
  return { name: group.name, description: group.description };
}

export function validateGroupDraft(draft: GroupDraft): void {
  const fields: Record<string, string[]> = {};
  const name = draft.name.trim();
  if (!name) fields.name = ["Name is required."];
  else if (name.length > 255) fields.name = ["Name must be 255 characters or fewer."];
  if (Object.keys(fields).length) {
    throw new LocalValidationError("Check the highlighted fields.", fields);
  }
}

export function createGroupInputFromDraft(draft: GroupDraft): CreateGroupInput {
  return { name: draft.name.trim(), description: draft.description };
}

export function updateGroupInputFromDraft(draft: GroupDraft): UpdateGroupInput {
  return { name: draft.name.trim(), description: draft.description };
}

export function groupDraftsEqual(left: GroupDraft, right: GroupDraft): boolean {
  return left.name.trim() === right.name.trim()
    && left.description === right.description;
}

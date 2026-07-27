import { isAtLeastLibrarian, type BookDetail, type CurrentUser } from "@second-pass/spl-api";

export function canEditBookGroups(user: CurrentUser, advancedGroupsEnabled: boolean): boolean {
  return advancedGroupsEnabled && isAtLeastLibrarian(user);
}

export function bookDetailWithUpdatedGroups(current: BookDetail, refreshed: BookDetail): BookDetail {
  return { ...current, groups: refreshed.groups };
}

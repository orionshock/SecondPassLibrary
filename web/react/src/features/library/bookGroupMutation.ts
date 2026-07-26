import { isAtLeastLibrarian, type BookDetail, type CurrentUser } from "@second-pass/spl-api";

export function canEditBookGroups(user: CurrentUser): boolean {
  return user.advancedLibraryGroupsEnabled && isAtLeastLibrarian(user);
}

export function bookDetailWithUpdatedGroups(current: BookDetail, refreshed: BookDetail): BookDetail {
  return { ...current, groups: refreshed.groups };
}

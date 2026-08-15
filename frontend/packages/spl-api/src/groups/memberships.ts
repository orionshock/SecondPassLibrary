import { apiClient, type ApiClient } from "../client";
import { toPage, type ApiPage, type Page } from "../pagination";
import { mapGroupMembership, mapMembershipError } from "./mappers";
import type { AddGroupMemberInput, GroupMembership, GroupMembersQuery, UpdateGroupMemberInput } from "./types";
import type { GroupMembershipResponse } from "./wire";

export async function listGroupMembers(groupId: string, query: GroupMembersQuery = {}, client: ApiClient = apiClient): Promise<Page<GroupMembership>> {
  const parameters = new URLSearchParams();
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  return toPage(
    await client.request<ApiPage<GroupMembershipResponse>>(`/api/v1/library/groups/${encodeURIComponent(groupId)}/memberships/${suffix}`),
    mapGroupMembership,
  );
}

export async function addGroupMember(groupId: string, input: AddGroupMemberInput, client: ApiClient = apiClient): Promise<GroupMembership> {
  try {
    return mapGroupMembership(await client.request<GroupMembershipResponse>(`/api/v1/library/groups/${encodeURIComponent(groupId)}/memberships/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: input.userId, is_curator: input.isCurator }),
    }));
  } catch (error: unknown) {
    throw mapMembershipError(error);
  }
}

export async function updateGroupMember(
  groupId: string,
  profileId: string,
  input: UpdateGroupMemberInput,
  client: ApiClient = apiClient,
): Promise<GroupMembership> {
  try {
    return mapGroupMembership(await client.request<GroupMembershipResponse>(membershipPath(groupId, profileId), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_curator: input.isCurator }),
    }));
  } catch (error: unknown) {
    throw mapMembershipError(error);
  }
}

export async function removeGroupMember(groupId: string, profileId: string, client: ApiClient = apiClient): Promise<void> {
  await client.request<void>(membershipPath(groupId, profileId), { method: "DELETE" });
}

function membershipPath(groupId: string, profileId: string): string {
  return `/api/v1/library/groups/${encodeURIComponent(groupId)}/memberships/${encodeURIComponent(profileId)}/`;
}

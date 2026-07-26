import {
  addGroupMember,
  listGroupMembers,
  listUserChoices,
  removeGroupMember,
  updateGroupMember,
  type GroupMembership,
  type LibraryGroup,
  type Page,
  type UserChoice,
} from "@second-pass/spl-api";
import { useEffect, useState } from "react";

import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { confirmGroupMemberRemoval } from "./groupBookMutation";
import { GroupMemberCandidatesPageRegion } from "./regions/GroupMemberCandidatesPageRegion";
import { GroupMembersEditPageRegion } from "./regions/GroupMembersEditPageRegion";

interface PageLoad<T> {
  page?: Page<T>;
  loading: boolean;
  error?: Error;
}

interface MemberMutation {
  pendingProfileId?: string;
  error?: Error;
  message?: string;
}

export function GroupMembersEditOrchestrator({ group, metadataPending, onMutationPendingChange }: {
  group: LibraryGroup;
  metadataPending: boolean;
  onMutationPendingChange: (pending: boolean) => void;
}) {
  const [membersPage, setMembersPage] = useState(1);
  const [membersPageSize, setMembersPageSize] = useState(20);
  const [membersLoad, setMembersLoad] = useState<PageLoad<GroupMembership>>({ loading: true });
  const [membersVersion, setMembersVersion] = useState(0);
  const [memberMutation, setMemberMutation] = useState<MemberMutation>({});
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [candidatePage, setCandidatePage] = useState(1);
  const [candidatePageSize, setCandidatePageSize] = useState(20);
  const [candidatesLoad, setCandidatesLoad] = useState<PageLoad<UserChoice>>({ loading: false });
  const [candidatesVersion, setCandidatesVersion] = useState(0);
  const [candidateMutation, setCandidateMutation] = useState<MemberMutation>({});

  useEffect(() => {
    let active = true;
    setMembersLoad((current) => ({ ...current, loading: true, error: undefined }));
    listGroupMembers(group.id, { page: membersPage, pageSize: membersPageSize })
      .then((page) => { if (active) setMembersLoad({ page, loading: false }); })
      .catch((error: unknown) => {
        if (active) setMembersLoad((current) => ({ ...current, loading: false, error: normalizeMutationError(error) }));
      });
    return () => { active = false; };
  }, [group.id, membersPage, membersPageSize, membersVersion]);

  useEffect(() => {
    if (!query) {
      setCandidatesLoad({ loading: false });
      return;
    }
    let active = true;
    setCandidatesLoad((current) => ({ ...current, loading: true, error: undefined }));
    listUserChoices({
      q: query,
      excludeGroupId: group.id,
      page: candidatePage,
      pageSize: candidatePageSize,
    }).then((page) => { if (active) setCandidatesLoad({ page, loading: false }); })
      .catch((error: unknown) => {
        if (active) setCandidatesLoad((current) => ({ ...current, loading: false, error: normalizeMutationError(error) }));
      });
    return () => { active = false; };
  }, [candidatePage, candidatePageSize, candidatesVersion, group.id, query]);

  function refreshAfterMutation() {
    setMembersVersion((value) => value + 1);
    if (query) setCandidatesVersion((value) => value + 1);
  }

  async function addMember(choice: UserChoice) {
    setCandidateMutation({ pendingProfileId: choice.profileId });
    try {
      await addGroupMember(group.id, { userId: choice.profileId, isCurator: false });
      setCandidateMutation({ message: "Member added." });
      setMembersVersion((value) => value + 1);
      if (candidatePage > 1 && candidatesLoad.page?.items.length === 1) setCandidatePage(candidatePage - 1);
      else setCandidatesVersion((value) => value + 1);
    } catch (error: unknown) {
      setCandidateMutation({ error: normalizeMutationError(error) });
    }
  }

  async function removeMember(membership: GroupMembership) {
    if (!confirmGroupMemberRemoval()) return;
    setMemberMutation({ pendingProfileId: membership.user.profileId });
    try {
      await removeGroupMember(group.id, membership.user.profileId);
      setMemberMutation({ message: "Member removed." });
      if (membersPage > 1 && membersLoad.page?.items.length === 1) {
        setMembersPage(membersPage - 1);
        if (query) setCandidatesVersion((value) => value + 1);
      } else refreshAfterMutation();
    } catch (error: unknown) {
      setMemberMutation({ error: normalizeMutationError(error) });
    }
  }

  async function toggleCurator(membership: GroupMembership) {
    if (group.isPublicGroup) return;
    setMemberMutation({ pendingProfileId: membership.user.profileId });
    try {
      await updateGroupMember(group.id, membership.user.profileId, {
        isCurator: !membership.isCurator,
      });
      setMemberMutation({ message: membership.isCurator ? "Curator access removed." : "Curator access granted." });
      refreshAfterMutation();
    } catch (error: unknown) {
      setMemberMutation({ error: normalizeMutationError(error) });
    }
  }

  const controlsDisabled = metadataPending
    || Boolean(memberMutation.pendingProfileId)
    || Boolean(candidateMutation.pendingProfileId);

  useEffect(() => {
    onMutationPendingChange(
      Boolean(memberMutation.pendingProfileId) || Boolean(candidateMutation.pendingProfileId),
    );
    return () => onMutationPendingChange(false);
  }, [candidateMutation.pendingProfileId, memberMutation.pendingProfileId, onMutationPendingChange]);

  return <div className="group-members-editor">
    {memberMutation.message ? <p className="group-edit-section-feedback" aria-live="polite">{memberMutation.message}</p> : null}
    <GroupMembersEditPageRegion
      page={membersLoad.page}
      pageNumber={membersPage}
      pageSize={membersPageSize}
      isPublicGroup={group.isPublicGroup}
      loading={membersLoad.loading}
      error={memberMutation.error ?? membersLoad.error}
      pendingProfileId={memberMutation.pendingProfileId}
      controlsDisabled={controlsDisabled}
      onToggleCurator={(membership) => void toggleCurator(membership)}
      onRemove={(membership) => void removeMember(membership)}
      onPageChange={setMembersPage}
      onPageSizeChange={(pageSize) => { setMembersPageSize(pageSize); setMembersPage(1); }}
      onRetry={() => { setMemberMutation({}); setMembersVersion((value) => value + 1); }}
    />
    {candidateMutation.message ? <p className="group-edit-section-feedback" aria-live="polite">{candidateMutation.message}</p> : null}
    <GroupMemberCandidatesPageRegion
      search={search}
      page={candidatesLoad.page}
      pageNumber={candidatePage}
      pageSize={candidatePageSize}
      loading={candidatesLoad.loading}
      error={candidateMutation.error ?? candidatesLoad.error}
      pendingProfileId={candidateMutation.pendingProfileId}
      controlsDisabled={controlsDisabled}
      onSearchChange={(value) => { setSearch(value); setCandidateMutation({}); }}
      onSearch={() => { setQuery(search.trim()); setCandidatePage(1); setCandidatesLoad({ loading: false }); }}
      onAdd={(choice) => void addMember(choice)}
      onPageChange={setCandidatePage}
      onPageSizeChange={(pageSize) => { setCandidatePageSize(pageSize); setCandidatePage(1); }}
      onRetry={() => { setCandidateMutation({}); setCandidatesVersion((value) => value + 1); }}
    />
  </div>;
}

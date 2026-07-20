import {
  listClientSessions,
  logoutOtherWebSessions,
  revokeClientSession,
  updateCurrentUser,
  type ClientSession,
  type UpdateCurrentUserInput,
} from "@second-pass/spl-api";
import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { breadcrumbNavigationState } from "../../app/navigation/breadcrumbs";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { PageHeader } from "../../components/ui";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import "../../shared/layout/AccountPageLayout.css";
import { AccountSessionsPageRegion } from "./regions/AccountSessionsPageRegion";
import { GroupMembershipsPageRegion } from "./regions/GroupMembershipsPageRegion";
import { ProfileDetailsPageRegion } from "./regions/ProfileDetailsPageRegion";
import "./Profile.css";
import { clientPairingBreadcrumbFallback, passwordBreadcrumbFallback, profileBreadcrumbFallback } from "./profileBreadcrumbs";
import { confirmClientSessionRevoke, confirmLogoutOtherWebSessions } from "./profileConfirmations";

export function ProfileOrchestrator() {
  usePageBreadcrumbs(profileBreadcrumbFallback);
  const { currentUser, onCurrentUserChange } = useOutletContext<AppOutletContext>();
  const [profileState, setProfileState] = useState<MutationState>(idleMutationState);
  const [sessions, setSessions] = useState<ClientSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [clientState, setClientState] = useState<MutationState>(idleMutationState);
  const [webState, setWebState] = useState<MutationState>(idleMutationState);

  useEffect(() => {
    let active = true;
    listClientSessions()
      .then((value) => { if (active) setSessions(value); })
      .catch((error) => { if (active) setClientState({ pending: false, error: normalizeMutationError(error) }); })
      .finally(() => { if (active) setSessionsLoading(false); });
    return () => { active = false; };
  }, []);

  async function saveProfile(input: UpdateCurrentUserInput) {
    setProfileState({ pending: true });
    try {
      const updated = await updateCurrentUser(input);
      onCurrentUserChange(updated);
      setProfileState({ pending: false, message: "Profile saved." });
    } catch (error: unknown) {
      setProfileState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function logoutOthers() {
    if (!confirmLogoutOtherWebSessions()) return;
    setWebState({ pending: true });
    try {
      await logoutOtherWebSessions();
      setWebState({ pending: false, message: "Other web sessions logged out." });
    } catch (error: unknown) {
      setWebState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function revokeSession(session: ClientSession) {
    if (!confirmClientSessionRevoke(session.name)) return;
    setClientState({ pending: true });
    try {
      await revokeClientSession(session.id);
      setSessions((current) => current.filter(({ id }) => id !== session.id));
      setClientState({ pending: false, message: `${session.name} revoked.` });
    } catch (error: unknown) {
      setClientState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  return <div className="page-stack account-page">
    <PageHeader title="Profile" actions={<Link className="button" to="/profile/password" state={breadcrumbNavigationState(passwordBreadcrumbFallback)}>Change password</Link>} />
    <ProfileDetailsPageRegion user={currentUser} state={profileState} onSave={saveProfile} onClearStatus={() => setProfileState(idleMutationState)} />
    <GroupMembershipsPageRegion user={currentUser} />
    <AccountSessionsPageRegion
      sessions={sessions}
      loading={sessionsLoading}
      clientState={clientState}
      webState={webState}
      clientPairingLinkState={breadcrumbNavigationState(clientPairingBreadcrumbFallback)}
      onLogoutOthers={logoutOthers}
      onRevokeSession={revokeSession}
    />
  </div>;
}

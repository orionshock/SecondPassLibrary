import {
  ApiError,
  enableAdvancedGroups,
  getServerSettings,
  updateGeneralSettings,
  updatePublicLibrarySettings,
  type GeneralServerSettings,
  type PublicLibrarySettings,
  type ServerSettings,
} from "@second-pass/spl-api";
import { useEffect, useState, type FormEvent } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { Button, ErrorPanel, PageHeader } from "../../components/ui";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { ActionRowComponent } from "../../shared/forms/ActionRowComponent";
import { GeneralSettingsPageRegion } from "./regions/GeneralSettingsPageRegion";
import { LibraryGroupsPageRegion } from "./regions/LibraryGroupsPageRegion";
import { PublicLibraryPageRegion } from "./regions/PublicLibraryPageRegion";
import { confirmEnableAdvancedGroups } from "./serverSettingsConfirmations";
import { serverSettingsFormId, serverSettingsSearchParams, serverSettingsTabFromSearchParams, serverSettingsTabs } from "./serverSettingsTabs";
import "./ServerSettings.css";

export const serverSettingsBreadcrumbFallback = [] as const;

interface SettingsLoadState {
  loading: boolean;
  settings?: ServerSettings;
  error?: Error;
  forbidden?: boolean;
}

export function ServerSettingsOrchestrator() {
  usePageBreadcrumbs(serverSettingsBreadcrumbFallback);
  const { currentUser, serverInfo, onServerInfoChange, refreshCurrentUser } = useOutletContext<AppOutletContext>();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const tab = serverSettingsTabFromSearchParams(searchParameters);
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<SettingsLoadState>({ loading: canAccessServerSettings(currentUser.isOwner), forbidden: !canAccessServerSettings(currentUser.isOwner) });
  const [editing, setEditing] = useState(false);
  const [state, setState] = useState<MutationState>(idleMutationState);
  const [generalDraft, setGeneralDraft] = useState<GeneralServerSettings>({ name: "", description: "", bannerText: "" });
  const [publicDraft, setPublicDraft] = useState<PublicLibrarySettings>({ name: "", description: "" });

  useEffect(() => {
    if (searchParameters.get("tab") !== tab) setSearchParameters(serverSettingsSearchParams(tab), { replace: true });
  }, [searchParameters, setSearchParameters, tab]);

  useEffect(() => {
    if (!canAccessServerSettings(currentUser.isOwner)) { setLoad({ loading: false, forbidden: true }); return; }
    let active = true;
    setLoad((value) => ({ ...value, loading: true, error: undefined }));
    getServerSettings()
      .then((settings) => {
        if (!active) return;
        setLoad({ loading: false, settings });
        setGeneralDraft(settings.general);
        setPublicDraft(settings.publicLibrary);
      })
      .catch((error: unknown) => {
        if (!active) return;
        setLoad({ loading: false, forbidden: error instanceof ApiError && error.status === 403, error: normalizeMutationError(error) });
      });
    return () => { active = false; };
  }, [currentUser.isOwner, retry]);

  useEffect(() => {
    setEditing(false);
    setState(idleMutationState);
    if (load.settings) {
      setGeneralDraft(load.settings.general);
      setPublicDraft(load.settings.publicLibrary);
    }
  }, [tab]);

  function selectTab(nextTab: typeof tab) {
    setSearchParameters(serverSettingsSearchParams(nextTab));
  }

  function cancel() {
    if (load.settings) {
      setGeneralDraft(load.settings.general);
      setPublicDraft(load.settings.publicLibrary);
    }
    setState(idleMutationState);
    setEditing(false);
  }

  async function saveGeneral(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState({ pending: true });
    try {
      const settings = await updateGeneralSettings(generalDraft);
      setLoad({ loading: false, settings });
      setGeneralDraft(settings.general);
      onServerInfoChange({ ...serverInfo, name: settings.general.name, description: settings.general.description });
      void refreshCurrentUser().catch(() => undefined);
      setEditing(false);
      setState({ pending: false, message: "General settings saved." });
    } catch (error: unknown) { setState({ pending: false, error: normalizeMutationError(error) }); }
  }

  async function savePublicLibrary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState({ pending: true });
    try {
      const settings = await updatePublicLibrarySettings(publicDraft);
      setLoad({ loading: false, settings });
      setPublicDraft(settings.publicLibrary);
      setEditing(false);
      setState({ pending: false, message: "Public Library saved." });
    } catch (error: unknown) { setState({ pending: false, error: normalizeMutationError(error) }); }
  }

  async function enableGroups() {
    if (!confirmEnableAdvancedGroups()) return;
    setState({ pending: true });
    try {
      const settings = await enableAdvancedGroups();
      setLoad({ loading: false, settings });
      void refreshCurrentUser().catch(() => undefined);
      setEditing(false);
      setState({ pending: false, message: "Advanced library groups enabled." });
    } catch (error: unknown) { setState({ pending: false, error: normalizeMutationError(error) }); }
  }

  if (load.forbidden) return <div className="server-settings-state-page"><ErrorPanel>Server Settings are available to the Owner only.</ErrorPanel></div>;
  if (load.loading && !load.settings) return <div className="server-settings-state-page" aria-busy="true">Loading server settings…</div>;
  if (load.error || !load.settings) return <div className="server-settings-state-page"><ErrorPanel>{load.error?.message ?? "Server settings are unavailable."}</ErrorPanel><Button type="button" onClick={() => setRetry((value) => value + 1)}>Retry</Button></div>;

  const settings = load.settings;
  const formId = serverSettingsFormId(tab);
  const headerActions = <ActionRowComponent state={state}>
    {editing ? <>
      <Button type="button" className="button--secondary" disabled={state.pending} onClick={cancel}>Cancel</Button>
      {formId ? <Button type="submit" form={formId} disabled={state.pending}>{state.pending ? "Saving..." : "Save"}</Button> : null}
    </> : <Button type="button" onClick={() => { setState(idleMutationState); setEditing(true); }}>Edit</Button>}
  </ActionRowComponent>;

  return <div className="page-stack server-settings-page">
    <PageHeader title="Server Settings" />
    <div className="server-settings-tabs">
      <div className="server-settings-tab-list" role="tablist" aria-label="Server settings sections">
        {serverSettingsTabs.map(({ id, label }) => <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => selectTab(id)}>{label}</button>)}
      </div>
      <div className="server-settings-tab-actions">{headerActions}</div>
    </div>
    {tab === "general" ? <GeneralSettingsPageRegion
      settings={settings.general}
      draft={generalDraft}
      editing={editing}
      state={state}
      onChange={(field, value) => setGeneralDraft((draft) => ({ ...draft, [field]: value }))}
      onSubmit={(event) => void saveGeneral(event)}
    /> : null}
    {tab === "public-library" ? <PublicLibraryPageRegion
      settings={settings.publicLibrary}
      draft={publicDraft}
      editing={editing}
      state={state}
      onChange={(field, value) => setPublicDraft((draft) => ({ ...draft, [field]: value }))}
      onSubmit={(event) => void savePublicLibrary(event)}
    /> : null}
    {tab === "library-groups" ? <LibraryGroupsPageRegion settings={settings.libraryGroups} editing={editing} state={state} onEnable={() => void enableGroups()} /> : null}
  </div>;
}

export function canAccessServerSettings(isOwner: boolean): boolean { return isOwner; }

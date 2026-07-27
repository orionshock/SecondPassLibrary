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
import { useLocation, useOutletContext, useSearchParams } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { Button, ErrorPanel } from "../../components/ui";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { ActionRowComponent } from "../../shared/forms/ActionRowComponent";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";
import { TabListComponent, tabButtonId, tabPanelId } from "../../shared/tabs/TabListComponent";
import { GeneralSettingsPageRegion } from "./regions/GeneralSettingsPageRegion";
import { LibraryGroupsPageRegion } from "./regions/LibraryGroupsPageRegion";
import { PublicLibraryPageRegion } from "./regions/PublicLibraryPageRegion";
import { DjangoAdminActionComponent } from "./DjangoAdminActionComponent";
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
  const location = useLocation();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const tab = serverSettingsTabFromSearchParams(searchParameters);
  const canonicalSearchParameters = serverSettingsSearchParams(searchParameters, tab);
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<SettingsLoadState>({ loading: canAccessServerSettings(currentUser.isOwner), forbidden: !canAccessServerSettings(currentUser.isOwner) });
  const [editing, setEditing] = useState(false);
  const [state, setState] = useState<MutationState>(idleMutationState);
  const [generalDraft, setGeneralDraft] = useState<GeneralServerSettings>({ name: "", description: "", bannerText: "" });
  const [publicDraft, setPublicDraft] = useState<PublicLibrarySettings>({ name: "", description: "" });

  useEffect(() => {
    if (searchParameters.toString() === canonicalSearchParameters.toString()) return;
    setSearchParameters(canonicalSearchParameters, { replace: true, state: location.state });
  }, [canonicalSearchParameters, location.state, searchParameters, setSearchParameters]);

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
    setSearchParameters(serverSettingsSearchParams(searchParameters, nextTab), { state: location.state });
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
      <Button type="button" tone="secondary" disabled={state.pending} onClick={cancel}>Cancel</Button>
      {formId ? <Button type="submit" form={formId} disabled={state.pending}>{state.pending ? "Saving..." : "Save"}</Button> : null}
    </> : <Button type="button" tone="secondary" onClick={() => { setState(idleMutationState); setEditing(true); }}>Edit</Button>}
  </ActionRowComponent>;

  return <ProductPageShellComponent className="server-settings-page" title="Server Settings" actions={<DjangoAdminActionComponent enabled={currentUser.canAccessDjangoAdmin} />}>
    <div className="server-settings-tabs">
      <TabListComponent tabs={serverSettingsTabs} activeTab={tab} onChange={selectTab} ariaLabel="Server settings sections" idPrefix="server-settings" />
      <div className="server-settings-tab-actions">{headerActions}</div>
    </div>
    <div id={tabPanelId("server-settings", tab)} role="tabpanel" aria-labelledby={tabButtonId("server-settings", tab)}>
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
    </div>
  </ProductPageShellComponent>;
}

export function canAccessServerSettings(isOwner: boolean): boolean { return isOwner; }

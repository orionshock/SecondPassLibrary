import {
  ApiError,
  enableAdvancedGroups,
  getServerSettings,
  updateExternalServicesSettings,
  updateServerIdentity,
  updatePublicLibrarySettings,
  type GeneralServerSettings,
  type PublicLibrarySettings,
  type ServerSettings,
} from "@second-pass/spl-api";
import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useOutletContext, useSearchParams } from "react-router";

import type { AppOutletContext } from "../../app/layout/AppOrchestrator";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { Button, ErrorPanel } from "../../components/UiPrimitives";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { useAutoDismissMutationMessage } from "../../shared/feedback/useAutoDismissMutationMessage";
import { ActionRow } from "../../shared/forms/ActionRow";
import { ProductPageShell } from "../../shared/layout/ProductPageShell";
import { TabList, tabButtonId, tabPanelId } from "../../shared/tabs/TabList";
import { GeneralSettingsPageRegion } from "./regions/GeneralSettingsPageRegion";
import { ExternalServicesPageRegion } from "./regions/ExternalServicesPageRegion";
import { LibraryGroupsPageRegion } from "./regions/LibraryGroupsPageRegion";
import { PublicLibraryPageRegion } from "./regions/PublicLibraryPageRegion";
import { DjangoAdminAction } from "./DjangoAdminAction";
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
  const { currentUser, serverInfo, refreshServerInfo } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const tab = serverSettingsTabFromSearchParams(searchParameters);
  const canonicalSearchParameters = serverSettingsSearchParams(searchParameters, tab);
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<SettingsLoadState>({ loading: canAccessServerSettings(currentUser.isOwner), forbidden: !canAccessServerSettings(currentUser.isOwner) });
  const [editing, setEditing] = useState(false);
  const [state, setState] = useState<MutationState>(idleMutationState);
  const [shellRefreshWarning, setShellRefreshWarning] = useState<string>();
  useAutoDismissMutationMessage(state, setState);
  const [generalDraft, setGeneralDraft] = useState<GeneralServerSettings>({ serverId: "", name: "", description: "", bannerText: "", secondPassReaderWebClientUrl: "", secondPassReaderWebClientUrlLocked: false });
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
    if (state.pending) return;
    setSearchParameters(serverSettingsSearchParams(searchParameters, nextTab), { state: location.state });
  }

  function cancel() {
    if (state.pending) return;
    if (load.settings) {
      setGeneralDraft(load.settings.general);
      setPublicDraft(load.settings.publicLibrary);
    }
    setState(idleMutationState);
    setEditing(false);
  }

  function refreshShellAfterSave() {
    setShellRefreshWarning(undefined);
    void refreshServerInfo().catch((error: unknown) => {
      console.warn("Server settings were saved, but the application shell refresh failed.", {
        failureClass: error instanceof Error ? error.name : typeof error,
      });
      setShellRefreshWarning(
        "Settings were saved, but the application shell could not be refreshed. Reload the page to update navigation and server details.",
      );
    });
  }

  async function saveServerIdentity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.pending) return;
    setState({ pending: true });
    try {
      const settings = await updateServerIdentity(generalDraft);
      setLoad({ loading: false, settings });
      setGeneralDraft(settings.general);
      refreshShellAfterSave();
      setEditing(false);
      setState({ pending: false, message: "Server identity saved." });
    } catch (error: unknown) { setState({ pending: false, error: normalizeMutationError(error) }); }
  }

  async function saveExternalServices(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.pending || generalDraft.secondPassReaderWebClientUrlLocked) return;
    setState({ pending: true });
    try {
      const settings = await updateExternalServicesSettings(generalDraft.secondPassReaderWebClientUrl);
      setLoad({ loading: false, settings });
      setGeneralDraft(settings.general);
      refreshShellAfterSave();
      setEditing(false);
      setState({ pending: false, message: "External services saved." });
    } catch (error: unknown) { setState({ pending: false, error: normalizeMutationError(error) }); }
  }

  async function savePublicLibrary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.pending) return;
    setState({ pending: true });
    try {
      const settings = await updatePublicLibrarySettings(publicDraft);
      setLoad({ loading: false, settings });
      setPublicDraft(settings.publicLibrary);
      refreshShellAfterSave();
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
      refreshShellAfterSave();
      setEditing(false);
      setState({ pending: false, message: "Advanced library groups enabled." });
    } catch (error: unknown) { setState({ pending: false, error: normalizeMutationError(error) }); }
  }

  if (load.forbidden) return <div className="server-settings-state-page"><ErrorPanel>Server Settings are available to the Owner only.</ErrorPanel></div>;
  if (load.loading && !load.settings) return <div className="server-settings-state-page" aria-busy="true">Loading server settings…</div>;
  if (load.error || !load.settings) return <div className="server-settings-state-page"><ErrorPanel>{load.error?.message ?? "Server settings are unavailable."}</ErrorPanel><Button type="button" onClick={() => setRetry((value) => value + 1)}>Retry</Button></div>;

  const settings = load.settings;
  const formId = serverSettingsFormId(tab);
  const headerActions = <ActionRow state={state}>
    {editing ? <>
      <Button type="button" tone="secondary" disabled={state.pending} onClick={cancel}>Cancel</Button>
      {formId ? <Button type="submit" form={formId} disabled={state.pending}>{state.pending ? "Saving..." : "Save"}</Button> : null}
    </> : <Button type="button" tone="secondary" onClick={() => { setState(idleMutationState); setEditing(true); }}>Edit</Button>}
  </ActionRow>;

  return <ProductPageShell className="server-settings-page" title="Server Settings" actions={<DjangoAdminAction enabled={currentUser.canAccessDjangoAdmin} />}>
    {shellRefreshWarning ? <p className="server-settings-refresh-warning" role="status">{shellRefreshWarning}</p> : null}
    <div className="server-settings-tabs">
      <TabList tabs={serverSettingsTabs} activeTab={tab} onChange={selectTab} ariaLabel="Server settings sections" disabled={state.pending} idPrefix="server-settings" />
      <div className="server-settings-tab-actions">{headerActions}</div>
    </div>
    <div id={tabPanelId("server-settings", tab)} role="tabpanel" aria-labelledby={tabButtonId("server-settings", tab)}>
    {tab === "general" ? <GeneralSettingsPageRegion
      settings={settings.general}
      serverUrls={serverInfo.serverUrls}
      draft={generalDraft}
      editing={editing}
      state={state}
      onChange={(field, value) => { if (!state.pending) setGeneralDraft((draft) => ({ ...draft, [field]: value })); }}
      onSubmit={(event) => void saveServerIdentity(event)}
    /> : null}
    {tab === "public-library" ? <PublicLibraryPageRegion
      settings={settings.publicLibrary}
      draft={publicDraft}
      editing={editing}
      state={state}
      onChange={(field, value) => { if (!state.pending) setPublicDraft((draft) => ({ ...draft, [field]: value })); }}
      onSubmit={(event) => void savePublicLibrary(event)}
    /> : null}
    {tab === "external-services" ? <ExternalServicesPageRegion
      settings={settings.general}
      draft={generalDraft}
      editing={editing}
      state={state}
      onChange={(value) => { if (!state.pending) setGeneralDraft((draft) => ({ ...draft, secondPassReaderWebClientUrl: value })); }}
      onSubmit={(event) => void saveExternalServices(event)}
    /> : null}
    {tab === "library-groups" ? <LibraryGroupsPageRegion settings={settings.libraryGroups} editing={editing} state={state} onEnable={() => void enableGroups()} /> : null}
    </div>
  </ProductPageShell>;
}

export function canAccessServerSettings(isOwner: boolean): boolean { return isOwner; }

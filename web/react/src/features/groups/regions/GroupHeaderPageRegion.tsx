import type { LibraryGroup } from "@second-pass/spl-api";
import { Link } from "react-router";

import { Badge, Button, ErrorPanel, PageHeader } from "../../../components/ui";
import { TabListComponent, type TabItem } from "../../../shared/tabs/TabListComponent";
import type { GroupDetailTab } from "../groupsQuery";

const groupDetailTabs: readonly TabItem<GroupDetailTab>[] = [
  { id: "books", label: "Books" },
  { id: "members", label: "Members" },
  { id: "shelves", label: "Shelves" },
];

export function GroupHeaderPageRegion({
  group,
  loading,
  error,
  isCurator,
  editPath,
  editNavigationState,
  activeTab,
  onTabChange,
  onRetry,
}: {
  group?: LibraryGroup;
  loading: boolean;
  error?: Error;
  isCurator: boolean;
  editPath?: string;
  editNavigationState?: unknown;
  activeTab: GroupDetailTab;
  onTabChange: (tab: GroupDetailTab) => void;
  onRetry: () => void;
}) {
  if (!group && loading) return <section className="group-detail-state" aria-live="polite" aria-busy="true">Loading group...</section>;
  if (!group && error) return <section className="group-detail-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!group) return null;

  return <>
    <PageHeader
      title={<span className="page-header__title-content">
        <span>{group.name}</span>
        {group.isPublicGroup ? <Badge tone="success">Public</Badge> : null}
        {isCurator ? <Badge tone="accent">Curator</Badge> : null}
      </span>}
      description={group.description || undefined}
      actions={editPath ? <Link className="button button--secondary" to={editPath} state={editNavigationState}>Manage</Link> : undefined}
    />
    <TabListComponent
      tabs={groupDetailTabs}
      activeTab={activeTab}
      onChange={onTabChange}
      ariaLabel="Group sections"
      idPrefix="group-detail"
    />
  </>;
}

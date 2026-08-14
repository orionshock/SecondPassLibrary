import type { LibraryGroup } from "@second-pass/spl-api";
import { Link } from "react-router";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Badge, Button, ErrorPanel, PageHeader } from "../../../components/UiPrimitives";
import { TabList, type TabItem } from "../../../shared/tabs/TabList";
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
  createShelfPath,
  createShelfNavigationState,
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
  createShelfPath?: string;
  createShelfNavigationState?: unknown;
  activeTab: GroupDetailTab;
  onTabChange: (tab: GroupDetailTab) => void;
  onRetry: () => void;
}) {
  if (!group && loading) return <section className="group-detail-state" aria-live="polite" aria-busy="true">Loading group...</section>;
  if (!group && error) return <section className="group-detail-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!group) return null;

  const showCreateShelf = activeTab === "shelves" && createShelfPath;

  return <div className="group-detail-header">
    <PageHeader
      title={<span className="page-header__title-content">
        <span>{group.name}</span>
        {group.isPublicGroup ? <Badge tone="success">Public</Badge> : null}
        {isCurator ? <Badge tone="accent">Curator</Badge> : null}
      </span>}
      description={group.description || undefined}
    />
    <TabList
      tabs={groupDetailTabs}
      activeTab={activeTab}
      onChange={onTabChange}
      ariaLabel="Group sections"
      idPrefix="group-detail"
    />
    {editPath || showCreateShelf ? <div className="group-detail-header__actions">
      {editPath ? <Link className="button button--secondary group-detail-header__manage" to={editPath} state={editNavigationState}>Manage</Link> : null}
      {showCreateShelf ? <Link
        className="button button--small button--secondary group-detail-header__create-shelf"
        to={createShelfPath}
        state={createShelfNavigationState}
      ><MaterialIcon name="add" size={16} />Create Shelf for Group</Link> : null}
    </div> : null}
  </div>;
}

import type { LibraryGroup } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { Badge, Button, ErrorPanel, PageHeader } from "../../../components/ui";
import type { GroupDetailTab } from "../groupsQuery";

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
    <nav className="group-detail-tabs" aria-label="Group sections">
      <Button type="button" aria-current={activeTab === "books" ? "page" : undefined} onClick={() => onTabChange("books")}>Books</Button>
      <Button type="button" aria-current={activeTab === "members" ? "page" : undefined} onClick={() => onTabChange("members")}>Members</Button>
      <Button type="button" aria-current={activeTab === "shelves" ? "page" : undefined} onClick={() => onTabChange("shelves")}>Shelves</Button>
    </nav>
  </>;
}

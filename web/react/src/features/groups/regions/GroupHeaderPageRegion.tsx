import type { LibraryGroup } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { Badge, Button, ErrorPanel } from "../../../components/ui";
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
    <header className="group-detail-header">
      <div className="group-detail-header__title">
        <h1>{group.name}</h1>
        {group.isPublicGroup ? <Badge tone="success">Public</Badge> : null}
        {isCurator ? <Badge tone="accent">Curator</Badge> : null}
      </div>
      {editPath ? <Link className="button group-detail-header__edit" to={editPath} state={editNavigationState}>Edit</Link> : null}
      {group.description ? <p>{group.description}</p> : null}
    </header>
    <nav className="group-detail-tabs" aria-label="Group sections">
      <Button type="button" aria-current={activeTab === "books" ? "page" : undefined} onClick={() => onTabChange("books")}>Books</Button>
      <Button type="button" aria-current={activeTab === "members" ? "page" : undefined} onClick={() => onTabChange("members")}>Members</Button>
    </nav>
  </>;
}

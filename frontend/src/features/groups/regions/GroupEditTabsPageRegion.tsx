import { TabList, type TabItem } from "../../../shared/tabs/TabList";
import type { GroupEditTab } from "../groupsQuery";

const groupEditTabs: readonly TabItem<GroupEditTab>[] = [
  { id: "details", label: "Details" },
  { id: "books", label: "Books" },
  { id: "add-books", label: "Add Books" },
  { id: "members", label: "Members" },
];

export function GroupEditTabsPageRegion({ activeTab, disabled = false, onTabChange }: {
  activeTab: GroupEditTab;
  disabled?: boolean;
  onTabChange: (tab: GroupEditTab) => void;
}) {
  return <TabList
    tabs={groupEditTabs}
    activeTab={activeTab}
    onChange={onTabChange}
    ariaLabel="Group management sections"
    disabled={disabled}
    idPrefix="group-edit"
  />;
}

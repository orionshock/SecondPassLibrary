import { TabList, type TabItem } from "../../../shared/tabs/TabList";
import type { BookEditTab } from "../bookTabs";

export function BookEditTabsPageRegion({ active, showGroups = false, disabled = false, onChange }: { active: BookEditTab; showGroups?: boolean; disabled?: boolean; onChange: (tab: BookEditTab) => void }) {
  const tabs: readonly TabItem<BookEditTab>[] = [
    { id: "book", label: "Book" },
    { id: "catalog", label: "Catalog" },
    { id: "authors-series", label: "Authors & Series" },
    ...(showGroups ? [{ id: "groups" as const, label: "Library Groups" }] : []),
    { id: "group-shelves", label: "Group Shelves" },
    { id: "identifiers", label: "Identifiers" },
  ];
  return <TabList tabs={tabs} activeTab={active} onChange={onChange} ariaLabel="Book edit sections" disabled={disabled} idPrefix="book-edit" />;
}

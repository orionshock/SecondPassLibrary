import { TabListComponent, type TabItem } from "../../../shared/tabs/TabListComponent";
import type { ShelfEditTab } from "../shelvesQuery";

const shelfEditTabs: readonly TabItem<ShelfEditTab>[] = [
  { id: "details", label: "Details" },
  { id: "books", label: "Books" },
  { id: "add-books", label: "Add Books" },
];

export function ShelfEditTabsPageRegion({ activeTab, disabled = false, onTabChange }: {
  activeTab: ShelfEditTab;
  disabled?: boolean;
  onTabChange: (tab: ShelfEditTab) => void;
}) {
  return <TabListComponent
    tabs={shelfEditTabs}
    activeTab={activeTab}
    onChange={onTabChange}
    ariaLabel="Shelf edit sections"
    disabled={disabled}
    idPrefix="shelf-edit"
  />;
}

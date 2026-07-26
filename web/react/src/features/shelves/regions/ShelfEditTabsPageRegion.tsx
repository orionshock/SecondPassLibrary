import type { ShelfEditTab } from "../shelvesQuery";

export function ShelfEditTabsPageRegion({ activeTab, onTabChange }: {
  activeTab: ShelfEditTab;
  onTabChange: (tab: ShelfEditTab) => void;
}) {
  return <nav className="shelf-edit-tabs" aria-label="Shelf edit sections">
    {([
      ["details", "Details"],
      ["books", "Books"],
      ["add-books", "Add Books"],
    ] as const).map(([tab, label]) => <button
      key={tab}
      type="button"
      className="button--secondary"
      aria-current={activeTab === tab ? "page" : undefined}
      onClick={() => onTabChange(tab)}
    >{label}</button>)}
  </nav>;
}

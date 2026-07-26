export type GroupEditTab = "details" | "books" | "add-books";

export function GroupEditTabsPageRegion({ activeTab, canMutateBooks, onTabChange }: {
  activeTab: GroupEditTab;
  canMutateBooks: boolean;
  onTabChange: (tab: GroupEditTab) => void;
}) {
  const tabs: Array<readonly [GroupEditTab, string]> = canMutateBooks
    ? [["details", "Details"], ["books", "Books"], ["add-books", "Add Books"]]
    : [["details", "Details"]];

  return <nav className="group-edit-tabs" aria-label="Group edit sections">
    {tabs.map(([tab, label]) => <button
      key={tab}
      type="button"
      className="button--secondary"
      aria-current={activeTab === tab ? "page" : undefined}
      onClick={() => onTabChange(tab)}
    >{label}</button>)}
  </nav>;
}

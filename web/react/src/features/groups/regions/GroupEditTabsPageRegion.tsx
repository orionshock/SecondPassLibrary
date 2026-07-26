export type GroupEditTab = "details" | "books" | "add-books" | "members";

export function GroupEditTabsPageRegion({ activeTab, canMutateBooks, canMutateMembers, onTabChange }: {
  activeTab: GroupEditTab;
  canMutateBooks: boolean;
  canMutateMembers: boolean;
  onTabChange: (tab: GroupEditTab) => void;
}) {
  const tabs: Array<readonly [GroupEditTab, string]> = [["details", "Details"]];
  if (canMutateBooks) tabs.push(["books", "Books"], ["add-books", "Add Books"]);
  if (canMutateMembers) tabs.push(["members", "Members"]);

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

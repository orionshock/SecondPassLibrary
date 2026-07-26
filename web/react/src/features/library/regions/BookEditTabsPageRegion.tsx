import { Button } from "../../../components/ui";

export type BookEditTab = "book" | "catalog" | "authors-series" | "identifiers" | "groups";

export function BookEditTabsPageRegion({ active, showGroups = false, onChange }: { active: BookEditTab; showGroups?: boolean; onChange: (tab: BookEditTab) => void }) {
  const tabs: Array<[BookEditTab, string]> = [
    ["book", "Book"],
    ["catalog", "Catalog"],
    ["authors-series", "Authors & Series"],
    ...(showGroups ? [["groups", "Library Groups"] as [BookEditTab, string]] : []),
    ["identifiers", "Identifiers"],
  ];
  return <div className="book-edit-tabs" role="tablist" aria-label="Book edit sections">
    {tabs.map(([id, label]) => <Button key={id} type="button" role="tab" aria-selected={active === id} className={active === id ? "active" : ""} onClick={() => onChange(id)}>{label}</Button>)}
  </div>;
}

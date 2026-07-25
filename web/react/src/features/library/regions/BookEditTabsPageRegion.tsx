import { Button } from "../../../components/ui";

export type BookEditTab = "book" | "catalog" | "authors-series" | "identifiers";

export function BookEditTabsPageRegion({ active, onChange }: { active: BookEditTab; onChange: (tab: BookEditTab) => void }) {
  const tabs: Array<[BookEditTab, string]> = [
    ["book", "Book"],
    ["catalog", "Catalog"],
    ["authors-series", "Authors & Series"],
    ["identifiers", "Identifiers"],
  ];
  return <div className="book-edit-tabs" role="tablist" aria-label="Book edit sections">
    {tabs.map(([id, label]) => <Button key={id} type="button" role="tab" aria-selected={active === id} className={active === id ? "active" : ""} onClick={() => onChange(id)}>{label}</Button>)}
  </div>;
}

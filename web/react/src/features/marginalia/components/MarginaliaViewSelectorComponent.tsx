import type { MarginaliaView } from "../marginaliaQuery";

const views: readonly { view: MarginaliaView; label: string }[] = [
  { view: "sessions", label: "Sessions" },
  { view: "books", label: "Books" },
];

export function MarginaliaViewSelectorComponent({ activeView, onViewChange }: {
  activeView: MarginaliaView;
  onViewChange: (view: MarginaliaView) => void;
}) {
  return <nav className="marginalia-view-selector" aria-label="Marginalia views">
    {views.map(({ view, label }) => <button
      key={view}
      type="button"
      className={activeView === view ? "active" : ""}
      aria-current={activeView === view ? "page" : undefined}
      onClick={() => onViewChange(view)}
    >{label}</button>)}
  </nav>;
}

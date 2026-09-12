import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import type { MarginaliaView } from "./marginaliaQuery";

const views: readonly { view: MarginaliaView; label: string; icon: string }[] = [
  { view: "sessions", label: "Sessions", icon: "history" },
  { view: "books", label: "Books", icon: "menu_book" },
];

export function MarginaliaViewSelector({ activeView, onViewChange }: {
  activeView: MarginaliaView;
  onViewChange: (view: MarginaliaView) => void;
}) {
  return <div className="marginalia-view-selector" role="group" aria-label="Marginalia views">
    {views.map(({ view, label, icon }) => <button
      key={view}
      type="button"
      className={activeView === view ? "active" : ""}
      aria-pressed={activeView === view}
      onClick={() => onViewChange(view)}
    ><MaterialIcon name={icon} /><span>{label}</span></button>)}
  </div>;
}

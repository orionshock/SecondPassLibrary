import { MaterialIcon } from "../../components/icons/MaterialIcon";
import "./BookComponents.css";

export function BookMetadata({ authors, series, publisher }: {
  authors: readonly string[];
  series?: string;
  publisher?: string;
}) {
  return <div className="book-metadata-component">
    {authors.length > 0 ? <MetadataItem icon="person" label="Authors" text={authors.join(", ")} /> : null}
    {series ? <MetadataItem icon="auto_stories" label="Series" text={series} /> : null}
    {publisher ? <MetadataItem icon="apartment" label="Publisher" text={publisher} /> : null}
  </div>;
}

function MetadataItem({ icon, label, text }: { icon: string; label: string; text: string }) {
  return <span className="book-metadata-component__item" aria-label={`${label}: ${text}`}>
    <MaterialIcon name={icon} /><span>{text}</span>
  </span>;
}

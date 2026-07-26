import { Link } from "react-router-dom";

import { BookCoverPreviewStripComponent, type BookCoverPreviewItem } from "../books/BookCoverPreviewStripComponent";
import { GroupBadgeComponent } from "../groups/GroupBadgeComponent";
import "./ShelfComponents.css";

export function ShelfSummaryRowComponent({ name, description, detailPath, navigationState, previewBooks, group }: {
  name: string;
  description: string;
  detailPath: string;
  navigationState?: unknown;
  previewBooks: readonly BookCoverPreviewItem[];
  group?: { name: string; isPublicGroup: boolean };
}) {
  const hasPreviews = previewBooks.length > 0;
  return <article className={`shelf-summary-row-component${hasPreviews ? "" : " shelf-summary-row-component--without-previews"}`}>
    <div className="shelf-summary-row-component__identity">
      <div className="shelf-summary-row-component__title">
        <h2><Link to={detailPath} state={navigationState}>{name}</Link></h2>
        {group ? <GroupBadgeComponent
          name={group.name}
          isPublicGroup={group.isPublicGroup}
        /> : null}
      </div>
      {description ? <p>{description}</p> : null}
    </div>
    {hasPreviews ? <BookCoverPreviewStripComponent books={previewBooks} /> : null}
  </article>;
}

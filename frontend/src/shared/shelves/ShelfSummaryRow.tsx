import { Link } from "react-router";

import { SanitizedRichText } from "../../components/SanitizedRichText";
import { BookCoverPreviewStrip, type BookCoverPreviewItem } from "../books/BookCoverPreviewStrip";
import { GroupBadge } from "../groups/GroupBadge";
import { UserInlineIdentity } from "../users/UserInlineIdentity";
import "./ShelfComponents.css";

export type ShelfOwnerBadge =
  | { kind: "group"; label: string; isPublicGroup?: boolean }
  | { kind: "user"; username: string };

export function ShelfSummaryRow({ name, description, itemCount, detailPath, navigationState, previewBooks, owner }: {
  name: string;
  description: string;
  itemCount: number;
  detailPath: string;
  navigationState?: unknown;
  previewBooks: readonly BookCoverPreviewItem[];
  owner?: ShelfOwnerBadge;
}) {
  const hasPreviews = previewBooks.length > 0;
  return <article className={`shelf-summary-row-component compact-cover-preview-row${hasPreviews ? "" : " compact-cover-preview-row--without-previews"}`}>
    <div className="shelf-summary-row-component__identity compact-cover-preview-row__primary">
      <div className="shelf-summary-row-component__title">
        <h2><Link to={detailPath} state={navigationState}>{name}</Link></h2>
        <span className="css-dot" aria-hidden="true" />
        {owner ? <span className="shelf-summary-row-component__owner-relation">
          {owner.kind === "user" ? "shared by" : "from"}
        </span> : null}
        {owner ? <span className="shelf-summary-row-component__source">
          {owner.kind === "group" ? <GroupBadge
            name={owner.label}
            isPublicGroup={owner.isPublicGroup}
          /> : <UserInlineIdentity username={owner.username} />}
        </span> : null}
        {owner ? <span className="css-dot" aria-hidden="true" /> : null}
        <span className="shelf-summary-row-component__count">
          {itemCount} {itemCount === 1 ? "book" : "books"}
        </span>
      </div>
      {description ? <SanitizedRichText html={description} className="sanitized-rich-text--compact shelf-summary-row-component__description" /> : null}
    </div>
    {hasPreviews ? <BookCoverPreviewStrip books={previewBooks} /> : null}
  </article>;
}

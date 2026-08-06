import { Link } from "react-router";

import { Badge } from "../../components/ui";
import { BookCoverPreviewStripComponent, type BookCoverPreviewItem } from "../books/BookCoverPreviewStripComponent";
import "./GroupRowComponent.css";

export interface GroupRowIdentity {
  name: string;
  description: string;
  isPublicGroup: boolean;
}

export function GroupRowComponent({ group, detailPath, navigationState, isCurator, previewBooks }: {
  group: GroupRowIdentity;
  detailPath: string;
  navigationState?: unknown;
  isCurator: boolean;
  previewBooks: readonly BookCoverPreviewItem[];
}) {
  const hasPreviews = previewBooks.length > 0;
  return <article className={`group-row-component compact-cover-preview-row${hasPreviews ? "" : " compact-cover-preview-row--without-previews"}`}>
    <div className="group-row-component__identity compact-cover-preview-row__primary">
      <div className="group-row-component__title">
        <h2><Link to={detailPath} state={navigationState}>{group.name}</Link></h2>
        {group.isPublicGroup ? <Badge tone="success">Public</Badge> : null}
        {isCurator ? <Badge tone="accent">Curator</Badge> : null}
      </div>
      {group.description ? <p>{group.description}</p> : null}
    </div>
    {hasPreviews ? <BookCoverPreviewStripComponent books={previewBooks} /> : null}
  </article>;
}

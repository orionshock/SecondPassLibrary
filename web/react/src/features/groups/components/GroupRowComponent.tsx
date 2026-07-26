import type { LibraryGroup } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { Badge } from "../../../components/ui";
import { BookCoverPreviewStripComponent, type BookCoverPreviewItem } from "../../../shared/books/BookCoverPreviewStripComponent";

export function GroupRowComponent({
  group,
  detailPath,
  navigationState,
  isCurator,
  previewBooks,
}: {
  group: LibraryGroup;
  detailPath: string;
  navigationState?: unknown;
  isCurator: boolean;
  previewBooks: readonly BookCoverPreviewItem[];
}) {
  return <article className="group-row-component">
    <div className="group-row-component__identity">
      <div className="group-row-component__title">
        <h2><Link to={detailPath} state={navigationState}>{group.name}</Link></h2>
        {group.isPublicGroup ? <Badge tone="success">Public</Badge> : null}
        {isCurator ? <Badge tone="accent">Curator</Badge> : null}
      </div>
      {group.description ? <p>{group.description}</p> : null}
    </div>
    <BookCoverPreviewStripComponent books={previewBooks} />
  </article>;
}

import { useState } from "react";

import { MaterialIcon } from "../../components/icons/MaterialIcon";
import "./BookComponents.css";

export function BookCoverComponent({ coverUrl, title }: { coverUrl: string | null; title: string }) {
  const [failedUrl, setFailedUrl] = useState<string>();
  const showImage = Boolean(coverUrl && coverUrl !== failedUrl);

  return <span className="book-cover-component">
    {showImage
      ? <img src={coverUrl!} alt={`Cover of ${title}`} loading="lazy" onError={() => setFailedUrl(coverUrl!)} />
      : <span className="book-cover-component__fallback" aria-label={`No cover available for ${title}`}><MaterialIcon name="book_2" /></span>}
  </span>;
}

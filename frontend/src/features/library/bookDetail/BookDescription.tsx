export function BookDescription({ sanitizedHtml }: { sanitizedHtml: string }) {
  if (!sanitizedHtml) return null;
  // Book.description is an HTML fragment sanitized at every server write boundary.
  return <div className="book-description" dangerouslySetInnerHTML={{ __html: sanitizedHtml }} />;
}

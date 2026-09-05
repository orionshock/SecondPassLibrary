import type { ElementType } from "react";

import "./SanitizedRichText.css";

export function SanitizedRichText({
  html,
  className = "",
  as: Container = "div",
}: {
  html: string;
  className?: string;
  as?: ElementType;
}) {
  if (!html) return null;
  // This boundary accepts only HTML already sanitized by the server allowlist.
  return <Container
    className={`sanitized-rich-text ${className}`.trim()}
    dangerouslySetInnerHTML={{ __html: html }}
  />;
}

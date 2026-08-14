import { useState } from "react";

const collapsedCharacterLimit = 240;

export function ClampedLibraryText({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const lines = text.split(/\r?\n/);
  const collapsible = text.length > collapsedCharacterLimit || lines.length > 3;
  const collapsedText = lines.slice(0, 3).join("\n").slice(0, collapsedCharacterLimit).trimEnd();

  return <div className="clamped-library-text-component">
    <p className="clamped-library-text-component__text">
      {collapsible && !expanded ? `${collapsedText}…` : text}
      {collapsible ? <>{" "}<button type="button" className="clamped-library-text-component__toggle" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>{expanded ? "Show less" : "Show more"}</button></> : null}
    </p>
  </div>;
}

import { useState } from "react";

import { SanitizedRichText } from "../../../components/SanitizedRichText";

const collapsedCharacterLimit = 240;

export function ClampedLibraryText({ html }: { html: string }) {
  const [expanded, setExpanded] = useState(false);
  const structuralBreaks = html.match(/<(?:br|li|p)\b/gi)?.length ?? 0;
  const collapsible = html.length > collapsedCharacterLimit || structuralBreaks > 3;

  return <div className="clamped-library-text-component">
    <SanitizedRichText
      html={html}
      className={collapsible && !expanded
        ? "clamped-library-text-component__content clamped-library-text-component__content--collapsed"
        : "clamped-library-text-component__content"}
    />
    {collapsible ? <button
      type="button"
      className="clamped-library-text-component__toggle"
      aria-expanded={expanded}
      onClick={() => setExpanded((value) => !value)}
    >{expanded ? "Show less" : "Show more"}</button> : null}
  </div>;
}

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ActionFeedback } from "../shared/feedback/ActionFeedback";
import { clearMatchingMutationMessage } from "../shared/feedback/useAutoDismissMutationMessage";

describe("ActionFeedback", () => {
  it("renders stable success feedback", () => {
    const markup = renderToStaticMarkup(<ActionFeedback state={{ pending: false, message: "Saved." }} />);
    expect(markup).toContain('role="status"');
    expect(markup).toContain("Saved.");
  });

  it("clears only the success message that scheduled dismissal", () => {
    expect(clearMatchingMutationMessage({ pending: false, message: "Saved." }, "Saved."))
      .toEqual({ pending: false, message: undefined });
    expect(clearMatchingMutationMessage({ pending: false, message: "A newer result." }, "Saved."))
      .toEqual({ pending: false, message: "A newer result." });
  });
});

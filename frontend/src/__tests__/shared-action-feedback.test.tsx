import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ActionFeedbackComponent } from "../shared/feedback/ActionFeedbackComponent";
import { clearMatchingMutationMessage } from "../shared/feedback/useAutoDismissMutationMessage";

describe("ActionFeedbackComponent", () => {
  it("renders stable success feedback", () => {
    const markup = renderToStaticMarkup(<ActionFeedbackComponent state={{ pending: false, message: "Saved." }} />);
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

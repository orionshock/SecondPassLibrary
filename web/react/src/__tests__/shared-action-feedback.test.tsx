import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ActionFeedbackComponent } from "../shared/feedback/ActionFeedbackComponent";

describe("ActionFeedbackComponent", () => {
  it("renders stable success feedback", () => {
    const markup = renderToStaticMarkup(<ActionFeedbackComponent state={{ pending: false, message: "Saved." }} />);
    expect(markup).toContain('role="status"');
    expect(markup).toContain("check_circle");
  });
});

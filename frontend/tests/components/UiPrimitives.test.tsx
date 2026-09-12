import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { FormField } from "../../src/components/UiPrimitives";

describe("FormField", () => {
  it("associates validation errors with the invalid control", () => {
    const markup = renderToStaticMarkup(<FormField label="Title" htmlFor="title" error="Title is required">
      <input id="title" aria-describedby="title-help" />
    </FormField>);

    expect(markup).toContain('aria-describedby="title-help title-error"');
    expect(markup).toContain('aria-invalid="true"');
    expect(markup).toContain('id="title-error"');
  });
});

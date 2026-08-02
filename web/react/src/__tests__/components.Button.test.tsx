import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Button, IconButton } from "../components/ui";

describe("Button primitives", () => {
  it("uses the medium primary contract by default and accepts small danger treatment", () => {
    const defaultButton = renderToStaticMarkup(<Button>Save</Button>);
    const dangerButton = renderToStaticMarkup(<Button size="small" tone="danger">Delete</Button>);

    expect(defaultButton).toContain("button--medium");
    expect(defaultButton).toContain("button--primary");
    expect(dangerButton).toContain("button--small");
    expect(dangerButton).toContain("button--danger");
  });

  it("keeps icon controls compact by default and supports medium success treatment", () => {
    const defaultButton = renderToStaticMarkup(<IconButton aria-label="Move" />);
    const successButton = renderToStaticMarkup(<IconButton aria-label="Add" size="medium" tone="success" />);

    expect(defaultButton).toContain("icon-button--small");
    expect(defaultButton).toContain("icon-button--secondary");
    expect(successButton).toContain("icon-button--medium");
    expect(successButton).toContain("icon-button--success");
  });
});

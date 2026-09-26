import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { GroupBadge } from "../../../src/shared/groups/GroupBadge";

describe("GroupBadge", () => {
  it("renders structural group identity with distinct Public semantics", () => {
    const ordinary = renderToStaticMarkup(<GroupBadge name="Editors" />);
    const publicGroup = renderToStaticMarkup(<GroupBadge name="Common Room" isPublicGroup />);
    const medium = renderToStaticMarkup(<GroupBadge name="Editors" size="medium" />);

    expect(ordinary).toContain('aria-label="Group: Editors"');
    expect(ordinary).toContain("Editors");
    expect(publicGroup).toContain('aria-label="Public group: Common Room"');
    expect(publicGroup).toContain("Common Room");
    expect(medium).toContain('aria-label="Group: Editors"');
  });
});


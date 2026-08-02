import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { GroupBadgeComponent } from "../shared/groups/GroupBadgeComponent";

describe("GroupBadgeComponent", () => {
  it("renders structural group identity with distinct Public semantics", () => {
    const ordinary = renderToStaticMarkup(<GroupBadgeComponent name="Editors" />);
    const publicGroup = renderToStaticMarkup(<GroupBadgeComponent name="Common Room" isPublicGroup />);
    const medium = renderToStaticMarkup(<GroupBadgeComponent name="Editors" size="medium" />);

    expect(ordinary).toContain('aria-label="Group: Editors"');
    expect(ordinary).toContain("Editors");
    expect(publicGroup).toContain('aria-label="Public group: Common Room"');
    expect(publicGroup).toContain("Common Room");
    expect(ordinary).toContain("group-badge-component--small");
    expect(medium).toContain("group-badge-component--medium");
    expect(medium).toContain('aria-label="Group: Editors"');
  });
});

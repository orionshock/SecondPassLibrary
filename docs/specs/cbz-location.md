# CBZ Location Profile

## Status

Future specification only. Second Pass Library does not currently parse,
validate, store as CBZ-aware data, import, export, or navigate these locators.
This document reserves a proposed syntax so future CBZ work can use the generic
Marginalia `location` field without another contract rename.

## Proposed syntax

```text
cbz:<page>
cbz:<page>@p:<x>,<y>
cbz:<page>@r:<x>,<y>,<width>,<height>
cbz:<page>@s:<x>,<y>,<size>
cbz:<page>@c:<x>,<y>,<radius>
cbz:<page>@poly:<x1>,<y1>;<x2>,<y2>;<x3>,<y3>;...
```

Examples:

```text
cbz:27
cbz:27@r:0.10,0.20,0.40,0.30
cbz:27@c:0.50,0.40,0.12
cbz:27@poly:0.12,0.18;0.44,0.20;0.51,0.47;0.20,0.53
```

## Coordinate semantics

Coordinates use normalized page-image space with a nominal range of `[0,1]`.
The origin is the top-left; x increases rightward and y increases downward.

- point: x,y identify the point;
- rectangle: x,y identify the top-left, followed by width,height;
- square: x,y identify the top-left, followed by size;
- circle: x,y identify the center, followed by radius;
- polygon: each x,y pair is an ordered vertex.

Ordinary x/y coordinates and rectangle width/height are relative to their
corresponding image axes. Square size and circle radius are relative to
`min(imageWidth, imageHeight)`.

One locator represents one contiguous target. Color, note, OCR text, and other
annotation metadata are not part of the locator. Annotation `text`, `prefix`,
and `suffix` are optional for CBZ because OCR is not assumed.

This proposal deliberately does not define multi-region locators, OCR-derived
anchoring, page-existence validation, panel semantics, or runtime parsing and
validation behavior.

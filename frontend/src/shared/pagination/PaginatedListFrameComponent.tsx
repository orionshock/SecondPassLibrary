import type { ReactNode } from "react";

import { PagerComponent, type PagerComponentProps } from "./PagerComponent";
import "./PaginatedListFrameComponent.css";

export interface PaginatedListFrameComponentProps extends Omit<PagerComponentProps, "ariaLabel" | "density"> {
  children: ReactNode;
  topControls?: ReactNode;
}

export function PaginatedListFrameComponent({ children, topControls, ...pagerProps }: PaginatedListFrameComponentProps) {
  return <div className="paginated-list-frame">
    <div className="paginated-list-frame__pager paginated-list-frame__pager--top">
      <PagerComponent {...pagerProps} density="compact" ariaLabel={`${pagerProps.itemLabel} pagination, top`} />
      {topControls ? <div className="paginated-list-frame__top-controls">{topControls}</div> : null}
    </div>
    <div className="paginated-list-frame__body">{children}</div>
    {pagerProps.count > 0 ? <div className="paginated-list-frame__pager paginated-list-frame__pager--bottom">
      <PagerComponent {...pagerProps} density="full" ariaLabel={`${pagerProps.itemLabel} pagination, bottom`} />
    </div> : null}
  </div>;
}

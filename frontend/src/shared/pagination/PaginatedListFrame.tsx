import type { ReactNode } from "react";

import { Pager, type PagerProps } from "./Pager";
import "./PaginatedListFrame.css";

export interface PaginatedListFrameProps extends Omit<PagerProps, "ariaLabel" | "density"> {
  children: ReactNode;
  topControls?: ReactNode;
  topPagerAction?: ReactNode;
}

export function PaginatedListFrame({ children, topControls, topPagerAction, ...pagerProps }: PaginatedListFrameProps) {
  return <div className="paginated-list-frame">
    <div className="paginated-list-frame__pager paginated-list-frame__pager--top">
      <Pager {...pagerProps} density="compact" ariaLabel={`${pagerProps.itemLabel} pagination, top`} actionPrefix={topPagerAction} />
      {topControls ? <div className="paginated-list-frame__top-controls">{topControls}</div> : null}
    </div>
    <div className="paginated-list-frame__body">{children}</div>
    {pagerProps.count > 0 ? <div className="paginated-list-frame__pager paginated-list-frame__pager--bottom">
      <Pager {...pagerProps} density="full" ariaLabel={`${pagerProps.itemLabel} pagination, bottom`} />
    </div> : null}
  </div>;
}

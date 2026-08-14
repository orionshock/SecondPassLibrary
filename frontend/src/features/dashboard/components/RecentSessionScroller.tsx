import type { RecentMarginaliaSession } from "@second-pass/spl-api";
import { useCallback, useLayoutEffect, useRef, useState } from "react";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { IconButton } from "../../../components/ui";
import { RecentSessionCoverCard } from "./RecentSessionCoverCard";

interface ScrollerState {
  hasOverflow: boolean;
  atStart: boolean;
  atEnd: boolean;
}

const initialScrollerState: ScrollerState = { hasOverflow: false, atStart: true, atEnd: true };

export function dashboardScrollerState(element: Pick<HTMLElement, "scrollLeft" | "scrollWidth" | "clientWidth">): ScrollerState {
  const remaining = element.scrollWidth - element.clientWidth - element.scrollLeft;
  const hasOverflow = element.scrollWidth > element.clientWidth + 1;
  return { hasOverflow, atStart: element.scrollLeft <= 1, atEnd: !hasOverflow || remaining <= 1 };
}

export function scrollDashboardScroller(element: Pick<HTMLElement, "clientWidth" | "scrollBy">, direction: -1 | 1) {
  element.scrollBy({ left: direction * Math.max(1, element.clientWidth * 0.85), behavior: "smooth" });
}

export function RecentSessionScroller({ items }: { items: RecentMarginaliaSession[] }) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const [scrollState, setScrollState] = useState<ScrollerState>(initialScrollerState);
  const updateScrollState = useCallback(() => {
    if (scrollerRef.current) setScrollState(dashboardScrollerState(scrollerRef.current));
  }, []);

  useLayoutEffect(() => {
    const scroller = scrollerRef.current;
    if (!scroller) return;
    updateScrollState();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(updateScrollState);
    observer?.observe(scroller);
    window.addEventListener("resize", updateScrollState);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", updateScrollState);
    };
  }, [items, updateScrollState]);

  return <div className={`dashboard-scroller${!scrollState.atStart ? " dashboard-scroller--more-before" : ""}${!scrollState.atEnd ? " dashboard-scroller--more-after" : ""}`}>
    {scrollState.hasOverflow ? <div className="dashboard-scroller__controls" role="group" aria-label="Recent reading controls">
      <IconButton className="dashboard-scroller__control dashboard-scroller__control--previous" type="button" aria-label="Previous reading sessions" title="Previous" disabled={scrollState.atStart} onClick={() => scrollerRef.current && scrollDashboardScroller(scrollerRef.current, -1)}><MaterialIcon name="chevron_left" /></IconButton>
      <IconButton className="dashboard-scroller__control dashboard-scroller__control--next" type="button" aria-label="Next reading sessions" title="Next" disabled={scrollState.atEnd} onClick={() => scrollerRef.current && scrollDashboardScroller(scrollerRef.current, 1)}><MaterialIcon name="chevron_right" /></IconButton>
    </div> : null}
    <div ref={scrollerRef} className="dashboard-scroller__track" aria-label="Recent reading sessions" tabIndex={0} onScroll={updateScrollState}>
      {items.slice(0, 50).map((item) => <RecentSessionCoverCard key={item.id} item={item} />)}
    </div>
  </div>;
}

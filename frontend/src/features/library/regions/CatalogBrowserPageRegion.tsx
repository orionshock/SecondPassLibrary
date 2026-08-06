import { useLayoutEffect, useRef, useState, type ReactNode } from "react";

export function CatalogBrowserPageRegion({ tagRail, children }: {
  tagRail: ReactNode;
  children: ReactNode;
}) {
  const resultsRef = useRef<HTMLDivElement>(null);
  const [stableResultsHeight, setStableResultsHeight] = useState(0);

  useLayoutEffect(() => {
    const results = resultsRef.current;
    if (!results || typeof ResizeObserver === "undefined") return;

    const retainTallestHeight = () => {
      const measuredHeight = Math.ceil(results.getBoundingClientRect().height);
      setStableResultsHeight((currentHeight) => retainTallestCatalogResultsHeight(currentHeight, measuredHeight));
    };
    retainTallestHeight();
    const observer = new ResizeObserver(retainTallestHeight);
    observer.observe(results);
    return () => observer.disconnect();
  }, []);

  return <div className="library-browser">
    {tagRail}
    <div
      ref={resultsRef}
      className="library-results-column"
      style={stableResultsHeight ? { minBlockSize: `${stableResultsHeight}px` } : undefined}
    >
      {children}
    </div>
  </div>;
}

export function retainTallestCatalogResultsHeight(currentHeight: number, measuredHeight: number): number {
  return Math.max(currentHeight, measuredHeight);
}

import { ApiError } from "@second-pass/spl-api";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";

export interface UrlCollectionLoad<TPage> {
  page?: TPage;
  loading: boolean;
  error?: unknown;
  reload: () => void;
  retry: () => void;
}

interface UrlCollectionRequest<TPage extends { count: number }> {
  scope: string;
  canonicalQuery: string;
  page: number;
  pageSize: number;
  loadPage: (page: number) => Promise<TPage>;
  queryForPage: (page: number) => string;
  locationState?: unknown;
  onPageRecovered?: (page: number) => void;
  enabled?: boolean;
}

/** Owns the request and URL-recovery state machine shared by paged collection routes. */
export function useUrlCollectionLifecycle<TPage extends { count: number }>({
  scope,
  canonicalQuery,
  page,
  pageSize,
  loadPage,
  queryForPage,
  locationState = null,
  onPageRecovered,
  enabled = true,
}: UrlCollectionRequest<TPage>): UrlCollectionLoad<TPage> {
  const [searchParameters, setSearchParameters] = useSearchParams();
  const currentQuery = searchParameters.toString();
  const [retryGeneration, setRetryGeneration] = useState(0);
  const [load, setLoad] = useState<Omit<UrlCollectionLoad<TPage>, "reload" | "retry">>({ loading: enabled });
  const requestGeneration = useRef(0);
  const loadedScope = useRef(scope);
  const recoveredRequests = useRef(new Set<string>());
  const loadPageRef = useRef(loadPage);
  const queryForPageRef = useRef(queryForPage);
  const locationStateRef = useRef(locationState);
  const onPageRecoveredRef = useRef(onPageRecovered);
  loadPageRef.current = loadPage;
  queryForPageRef.current = queryForPage;
  locationStateRef.current = locationState;
  onPageRecoveredRef.current = onPageRecovered;

  useEffect(() => {
    if (!enabled || currentQuery === canonicalQuery) return;
    setSearchParameters(new URLSearchParams(canonicalQuery), {
      replace: true,
      state: locationStateRef.current,
    });
  }, [canonicalQuery, currentQuery, enabled, setSearchParameters]);

  useEffect(() => {
    if (!enabled || currentQuery !== canonicalQuery) return;
    const generation = ++requestGeneration.current;
    const requestPage = loadPageRef.current;
    const recoveredQueryForPage = queryForPageRef.current;
    const replacementState = locationStateRef.current;
    const publishRecoveredPage = onPageRecoveredRef.current;
    setLoad((current) => ({ page: loadedScope.current === scope ? current.page : undefined, loading: true }));

    void requestPage(page)
      .then((result) => {
        if (requestGeneration.current === generation) {
          loadedScope.current = scope;
          setLoad({ page: result, loading: false });
        }
      })
      .catch(async (error: unknown) => {
        if (requestGeneration.current !== generation) return;
        const recoveryKey = `${scope}:${canonicalQuery}`;
        if (!(error instanceof ApiError) || error.status !== 404 || page <= 1 || recoveredRequests.current.has(recoveryKey)) {
          setLoad((current) => ({ page: current.page, loading: false, error }));
          return;
        }

        recoveredRequests.current.add(recoveryKey);
        try {
          const firstPage = await requestPage(1);
          const correctedPage = Math.max(1, Math.ceil(firstPage.count / pageSize));
          const result = correctedPage === 1 ? firstPage : await requestPage(correctedPage);
          if (requestGeneration.current !== generation) return;
          // Let a coordinating workflow retain this authoritative correction while locked.
          publishRecoveredPage?.(correctedPage);
          const recoveredQuery = recoveredQueryForPage(correctedPage);
          recoveredRequests.current.add(`${scope}:${recoveredQuery}`);
          loadedScope.current = scope;
          setLoad({ page: result, loading: false });
          setSearchParameters(new URLSearchParams(recoveredQuery), {
            replace: true,
            state: replacementState,
          });
        } catch (recoveryError: unknown) {
          if (requestGeneration.current === generation) {
            setLoad((current) => ({ page: current.page, loading: false, error: recoveryError }));
          }
        }
      });

    return () => {
      if (requestGeneration.current === generation) requestGeneration.current += 1;
    };
  }, [canonicalQuery, currentQuery, enabled, page, pageSize, retryGeneration, scope, setSearchParameters]);

  const retry = useCallback(() => setRetryGeneration((current) => current + 1), []);
  const reload = useCallback(() => {
    recoveredRequests.current.delete(`${scope}:${canonicalQuery}`);
    setRetryGeneration((current) => current + 1);
  }, [canonicalQuery, scope]);
  return { ...load, reload, retry };
}

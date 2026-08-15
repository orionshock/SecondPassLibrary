import type { MarginaliaPageQuery, MarginaliaSessionsQuery } from "./types";

export function pageQuery(query: MarginaliaPageQuery): URLSearchParams {
  const parameters = new URLSearchParams();
  if (query.q !== undefined) parameters.set("q", query.q);
  if (query.page !== undefined) parameters.set("page", String(query.page));
  if (query.pageSize !== undefined) parameters.set("page_size", String(query.pageSize));
  return parameters;
}

export function sessionQuery(query: MarginaliaSessionsQuery): URLSearchParams {
  const parameters = pageQuery(query);
  if (query.status !== undefined) parameters.set("status", query.status);
  if (query.hasAnnotations !== undefined) parameters.set("has_annotations", String(query.hasAnnotations));
  return parameters;
}

export function withQuery(path: string, parameters: URLSearchParams): string {
  return parameters.size ? `${path}?${parameters.toString()}` : path;
}
export function bookPath(bookId: string): string { return `/api/v1/marginalia/books/${encodeURIComponent(bookId)}/`; }
export function sessionPath(sessionId: string): string { return `/api/v1/marginalia/sessions/${encodeURIComponent(sessionId)}/`; }
export function jsonRequest(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

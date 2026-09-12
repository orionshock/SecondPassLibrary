export interface ApiErrorDetails {
  code?: string;
  fields?: Record<string, string[]>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly fields?: Record<string, string[]>;

  constructor(message: string, status: number, details: ApiErrorDetails = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = details.code;
    this.fields = details.fields;
  }
}

export class NetworkError extends Error {
  constructor(message = "Can't reach the server. Check your connection and try again.") {
    super(message);
    this.name = "NetworkError";
  }
}

export type ApiErrorKind = "authentication" | "validation" | "network" | "unknown";

export function classifyApiError(error: unknown): ApiErrorKind {
  if (error instanceof NetworkError) return "network";
  if (!(error instanceof ApiError)) return "unknown";
  if (error.status === 401 || error.status === 403) return "authentication";
  if (error.status >= 400 && error.status < 500) return "validation";
  return "unknown";
}

export function isAuthenticationError(error: unknown): boolean {
  return classifyApiError(error) === "authentication";
}

type ErrorPayload = {
  detail?: unknown;
  code?: unknown;
  errors?: unknown;
  error?: unknown;
};

export function apiErrorFromPayload(status: number, payload: unknown): ApiError {
  const body = isRecord(payload) ? (payload as ErrorPayload) : {};
  const bounded = isRecord(body.error) ? body.error : {};
  const code = typeof bounded.code === "string"
    ? bounded.code
    : typeof body.code === "string"
      ? body.code
      : undefined;
  const fieldPayload = Object.fromEntries(
    Object.entries(body).filter(([key]) => !["detail", "code", "error", "errors"].includes(key)),
  );
  const fields = normalizeFieldErrors(body.errors) ?? normalizeFieldErrors(fieldPayload);
  const customMessage = boundedText(bounded.message);
  const hint = boundedText(bounded.hint);
  const message = customMessage
    ? `${customMessage}${hint ? ` ${hint}` : ""}`
    : apiErrorMessage(status, Boolean(fields));
  return new ApiError(message, status, { code, fields });
}

export function apiErrorMessage(status: number, hasFieldErrors = false): string {
  if (status === 400 && hasFieldErrors) return "Check the highlighted fields and try again.";
  if (status === 400 || status === 422) return "Check your entries and try again.";
  if (status === 401) return "Your session has ended. Log in and try again.";
  if (status === 403) return "You don't have permission to do that.";
  if (status === 404) return "This item is no longer available. Return to the list and try again.";
  if (status === 409) return "This item changed before your request finished. Reload and try again.";
  if (status === 413) return "The request is too large. Choose a smaller file or selection and try again.";
  if (status === 429) return "Too many requests. Wait a moment and try again.";
  return "The server couldn't complete the request. Try again. If it keeps failing, check the server logs.";
}

function boundedText(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const normalized = value.trim().replace(/\s+/g, " ");
  return normalized && normalized.length <= 500 ? normalized : undefined;
}

function normalizeFieldErrors(value: unknown): Record<string, string[]> | undefined {
  if (Array.isArray(value)) {
    const fields: Record<string, string[]> = {};
    for (const item of value) {
      if (!isRecord(item) || typeof item.path !== "string" || typeof item.message !== "string") continue;
      const path = importErrorPath(item.path);
      fields[path] = [...(fields[path] ?? []), item.message];
    }
    return Object.keys(fields).length > 0 ? fields : undefined;
  }
  if (!isRecord(value)) return undefined;

  const fields: Record<string, string[]> = {};
  for (const [field, messages] of Object.entries(value)) {
    collectFieldErrors(fields, toAppFieldName(field), messages);
  }
  return Object.keys(fields).length > 0 ? fields : undefined;
}

function importErrorPath(path: string): string {
  const field = path.startsWith("$.") ? path.slice(2) : path === "$" ? "file" : path;
  return toAppFieldName(field);
}

function collectFieldErrors(fields: Record<string, string[]>, path: string, value: unknown): void {
  if (typeof value === "string") {
    fields[path] = [...(fields[path] ?? []), value];
    return;
  }
  if (Array.isArray(value)) {
    const messages = value.filter((item): item is string => typeof item === "string");
    if (messages.length) fields[path] = [...(fields[path] ?? []), ...messages];
    value.forEach((item, index) => {
      if (typeof item !== "string") collectFieldErrors(fields, `${path}.${index}`, item);
    });
    return;
  }
  if (!isRecord(value)) return;
  for (const [field, messages] of Object.entries(value)) {
    collectFieldErrors(fields, `${path}.${toAppFieldName(field)}`, messages);
  }
}

function toAppFieldName(field: string): string {
  return field.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

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
  constructor(message = "The server could not be reached.") {
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
};

export function apiErrorFromPayload(status: number, payload: unknown): ApiError {
  const body = isRecord(payload) ? (payload as ErrorPayload) : {};
  const message = typeof body.detail === "string" ? body.detail : "The server could not complete the request.";
  const code = typeof body.code === "string" ? body.code : undefined;
  const fieldPayload = Object.fromEntries(
    Object.entries(body).filter(([key]) => !["detail", "code", "errors"].includes(key)),
  );
  const fields = normalizeFieldErrors(body.errors) ?? normalizeFieldErrors(fieldPayload);
  return new ApiError(message, status, { code, fields });
}

function normalizeFieldErrors(value: unknown): Record<string, string[]> | undefined {
  if (!isRecord(value)) return undefined;

  const fields: Record<string, string[]> = {};
  for (const [field, messages] of Object.entries(value)) {
    collectFieldErrors(fields, toAppFieldName(field), messages);
  }
  return Object.keys(fields).length > 0 ? fields : undefined;
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

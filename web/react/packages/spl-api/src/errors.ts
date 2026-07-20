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

type ErrorPayload = {
  detail?: unknown;
  code?: unknown;
  errors?: unknown;
};

export function apiErrorFromPayload(status: number, payload: unknown): ApiError {
  const body = isRecord(payload) ? (payload as ErrorPayload) : {};
  const message = typeof body.detail === "string" ? body.detail : "The server could not complete the request.";
  const code = typeof body.code === "string" ? body.code : undefined;
  const fields = normalizeFieldErrors(body.errors);
  return new ApiError(message, status, { code, fields });
}

function normalizeFieldErrors(value: unknown): Record<string, string[]> | undefined {
  if (!isRecord(value)) return undefined;

  const fields: Record<string, string[]> = {};
  for (const [field, messages] of Object.entries(value)) {
    if (Array.isArray(messages)) {
      fields[field] = messages.filter((message): message is string => typeof message === "string");
    } else if (typeof messages === "string") {
      fields[field] = [messages];
    }
  }
  return Object.keys(fields).length > 0 ? fields : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

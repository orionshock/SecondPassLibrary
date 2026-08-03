import { ApiError, NetworkError, apiErrorFromPayload } from "./errors";

export interface ApiClient {
  request<T>(path: string, init?: RequestInit, errorMapper?: ApiErrorMapper): Promise<T>;
}

export type ApiErrorMapper = (status: number, payload: unknown) => ApiError;

export interface AttachmentDownload {
  blob: Blob;
  filename: string;
  contentType: string;
}

export interface AttachmentApiClient {
  requestAttachment(path: string, init?: RequestInit, fallbackFilename?: string): Promise<AttachmentDownload>;
}

type CsrfTokenProvider = () => string | undefined;

export function createApiClient(
  fetchImplementation: typeof fetch = fetch,
  csrfTokenProvider: CsrfTokenProvider = browserCsrfToken,
): ApiClient & AttachmentApiClient {
  async function send(path: string, init: RequestInit, accept: string): Promise<Response> {
    const headers = new Headers(init.headers);
    headers.set("Accept", accept);
    const method = (init.method ?? "GET").toUpperCase();
    if (!new Set(["GET", "HEAD", "OPTIONS", "TRACE"]).has(method)) {
      const csrfToken = csrfTokenProvider();
      if (csrfToken) headers.set("X-CSRFToken", csrfToken);
    }

    try {
      return await fetchImplementation(path, {
        ...init,
        credentials: "same-origin",
        headers,
      });
    } catch {
      throw new NetworkError();
    }
  }

  return {
    async request<T>(
      path: string,
      init: RequestInit = {},
      errorMapper: ApiErrorMapper = apiErrorFromPayload,
    ): Promise<T> {
      const response = await send(path, init, "application/json");
      const payload = await parseJson(response);

      if (!response.ok) throw errorMapper(response.status, payload);
      return payload as T;
    },
    async requestAttachment(path: string, init: RequestInit = {}, fallbackFilename = "download") {
      const response = await send(path, init, "application/json, application/octet-stream");
      if (!response.ok) {
        const contentType = response.headers.get("content-type") ?? "";
        if (contentType.includes("application/json")) {
          let payload: unknown;
          try {
            payload = await response.json();
          } catch {
            throw new ApiError("The server returned invalid JSON.", response.status);
          }
          throw apiErrorFromPayload(response.status, payload);
        }
        throw new ApiError("The server could not complete the request.", response.status);
      }
      const contentType = response.headers.get("content-type") ?? "application/octet-stream";
      return {
        blob: await response.blob(),
        filename: attachmentFilename(response.headers.get("content-disposition"), fallbackFilename),
        contentType,
      };
    },
  };
}

function attachmentFilename(contentDisposition: string | null, fallback: string): string {
  const encoded = contentDisposition?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const plain = contentDisposition?.match(/filename=(?:"([^"]+)"|([^;]+))/i);
  let candidate = encoded ?? plain?.[1] ?? plain?.[2] ?? fallback;
  if (encoded) {
    try {
      candidate = decodeURIComponent(encoded);
    } catch {
      candidate = fallback;
    }
  }
  candidate = candidate.trim().split(/[\\/]/).pop()?.replace(/[\u0000-\u001f\u007f]/g, "") ?? "";
  return candidate || fallback;
}

function browserCsrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  return document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith("csrftoken="))
    ?.slice("csrftoken=".length);
}

async function parseJson(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new ApiError("The server returned an unexpected response.", response.status);
  }

  try {
    return await response.json();
  } catch {
    throw new ApiError("The server returned invalid JSON.", response.status);
  }
}

export const apiClient = createApiClient();

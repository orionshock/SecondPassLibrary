import { ApiError, NetworkError, apiErrorFromPayload } from "./errors";

export interface ApiClient {
  request<T>(path: string, init?: RequestInit): Promise<T>;
}

type CsrfTokenProvider = () => string | undefined;

export function createApiClient(
  fetchImplementation: typeof fetch = fetch,
  csrfTokenProvider: CsrfTokenProvider = browserCsrfToken,
): ApiClient {
  return {
    async request<T>(path: string, init: RequestInit = {}): Promise<T> {
      const headers = new Headers(init.headers);
      headers.set("Accept", "application/json");
      const method = (init.method ?? "GET").toUpperCase();
      if (!new Set(["GET", "HEAD", "OPTIONS", "TRACE"]).has(method)) {
        const csrfToken = csrfTokenProvider();
        if (csrfToken) headers.set("X-CSRFToken", csrfToken);
      }

      let response: Response;
      try {
        response = await fetchImplementation(path, {
          ...init,
          credentials: "same-origin",
          headers,
        });
      } catch {
        throw new NetworkError();
      }
      const payload = await parseJson(response);

      if (!response.ok) throw apiErrorFromPayload(response.status, payload);
      return payload as T;
    },
  };
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

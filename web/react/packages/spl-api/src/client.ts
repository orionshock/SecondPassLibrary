import { ApiError, NetworkError, apiErrorFromPayload } from "./errors";

export interface ApiClient {
  request<T>(path: string, init?: RequestInit): Promise<T>;
}

export function createApiClient(fetchImplementation: typeof fetch = fetch): ApiClient {
  return {
    async request<T>(path: string, init: RequestInit = {}): Promise<T> {
      const headers = new Headers(init.headers);
      headers.set("Accept", "application/json");

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

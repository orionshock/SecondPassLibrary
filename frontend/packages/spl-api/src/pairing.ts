import { apiClient, type ApiClient } from "./client";

interface PairingResponse {
  code: string;
  client_name: string;
  client_type: string;
  expires_at: string;
}

export interface ClientPairingRequest {
  code: string;
  clientName: string;
  clientType: string;
  expiresAt: string;
}

export async function lookupClientPairing(
  code: string,
  client: ApiClient = apiClient,
): Promise<ClientPairingRequest> {
  const response = await client.request<PairingResponse>("/api/v1/client-api/pairing/lookup/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  return {
    code: response.code,
    clientName: response.client_name,
    clientType: response.client_type,
    expiresAt: response.expires_at,
  };
}

export async function decideClientPairing(
  input: { code: string; action: "approve" | "deny"; clientName?: string },
  client: ApiClient = apiClient,
): Promise<"approved" | "denied"> {
  const response = await client.request<{ status: "approved" | "denied" }>(
    "/api/v1/client-api/pairing/decision/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code: input.code,
        action: input.action,
        ...(input.clientName === undefined ? {} : { client_name: input.clientName }),
      }),
    },
  );
  return response.status;
}

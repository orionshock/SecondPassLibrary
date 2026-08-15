import { apiClient, type ApiClient } from "../client";
import { mapAnnotation } from "./mappers";
import { sessionPath } from "./requests";
import type { MarginaliaAnnotation } from "./types";
import type { AnnotationCollectionResponse } from "./wire";

export async function listMarginaliaSessionAnnotations(sessionId: string, client: ApiClient = apiClient): Promise<MarginaliaAnnotation[]> {
  const response = await client.request<AnnotationCollectionResponse>(`${sessionPath(sessionId)}annotations/`);
  return response.annotations.map(mapAnnotation);
}

import { apiClient, type AttachmentApiClient, type AttachmentDownload } from "../client";
import { ApiError, apiErrorFromPayload } from "../errors";
import { jsonRequest, withQuery } from "./requests";

export interface CompleteMarginaliaExportInput { includeEmptySessions?: boolean; }
export interface SelectedMarginaliaExportInput extends CompleteMarginaliaExportInput { readingSessionIds: string[]; }
export type MarginaliaExportMode = "full" | "selected";
export type MarginaliaExportLimitKind = "selected_sessions" | "full_sessions" | "annotations" | "estimated_archive_bytes" | "archive_bytes";

export class MarginaliaExportTooLargeError extends ApiError {
  readonly guidance: string;
  readonly exportMode: MarginaliaExportMode;
  readonly limitKind: MarginaliaExportLimitKind;
  readonly maximum: number;

  constructor(input: { message: string; guidance: string; exportMode: MarginaliaExportMode; limitKind: MarginaliaExportLimitKind; maximum: number }) {
    super(input.message, 413, { code: "EXPORT_TOO_LARGE" });
    this.name = "MarginaliaExportTooLargeError";
    this.guidance = input.guidance;
    this.exportMode = input.exportMode;
    this.limitKind = input.limitKind;
    this.maximum = input.maximum;
  }
}

export function downloadCompleteMarginaliaExport(
  input: CompleteMarginaliaExportInput = {},
  client: AttachmentApiClient = apiClient,
): Promise<AttachmentDownload> {
  const parameters = new URLSearchParams();
  if (input.includeEmptySessions) parameters.set("include_empty_sessions", "true");
  return client.requestAttachment(withQuery("/api/v1/marginalia/export/", parameters), undefined, "second-pass-marginalia.json", marginaliaExportErrorFromPayload);
}

export function downloadSelectedMarginaliaExport(input: SelectedMarginaliaExportInput, client: AttachmentApiClient = apiClient): Promise<AttachmentDownload> {
  return client.requestAttachment(
    "/api/v1/marginalia/export/",
    jsonRequest("POST", { reading_session_ids: input.readingSessionIds, include_empty_sessions: input.includeEmptySessions ?? false }),
    "second-pass-marginalia.json",
    marginaliaExportErrorFromPayload,
  );
}

function marginaliaExportErrorFromPayload(status: number, payload: unknown): ApiError {
  const fallback = apiErrorFromPayload(status, payload);
  if (status !== 413 || fallback.code !== "EXPORT_TOO_LARGE" || !isRecord(payload)) return fallback;
  const error = payload.error;
  if (!isRecord(error) || !isRecord(error.limit)) return fallback;
  const guidance = error.hint;
  const exportMode = error.export_mode;
  const limitKind = error.limit.kind;
  const maximum = error.limit.maximum;
  if (
    typeof guidance !== "string" || !guidance
    || (exportMode !== "full" && exportMode !== "selected")
    || !isMarginaliaExportLimitKind(limitKind)
    || typeof maximum !== "number" || !Number.isSafeInteger(maximum) || maximum < 1
  ) return fallback;
  return new MarginaliaExportTooLargeError({ message: fallback.message, guidance, exportMode, limitKind, maximum });
}

function isMarginaliaExportLimitKind(value: unknown): value is MarginaliaExportLimitKind {
  return typeof value === "string" && new Set<MarginaliaExportLimitKind>([
    "selected_sessions",
    "full_sessions",
    "annotations",
    "estimated_archive_bytes",
    "archive_bytes",
  ]).has(value as MarginaliaExportLimitKind);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

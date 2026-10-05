import type { MarginaliaSessionEnvelope, MarginaliaSessionMetadataInput } from "@second-pass/spl-api";
import type { BrowserDownload } from "../../../shared/browser/saveDownloadedFile";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../../shared/feedback/mutationState";

type SessionDetailMutationKind = "name" | "note" | "close" | "delete" | "export";
type MetadataField = "name" | "notes";

interface SessionDetailMutationToken {
  readonly kind: SessionDetailMutationKind;
  readonly sessionId: string;
  readonly lifetime: number;
  readonly revision: number;
  readonly lifecycleRevision: number;
}

type SessionDetailMutationSettlement = "publish" | "discard" | "expired";

interface SessionDetailMutationAdapters {
  update: (sessionId: string, input: MarginaliaSessionMetadataInput) => Promise<MarginaliaSessionEnvelope>;
  close: (sessionId: string) => Promise<MarginaliaSessionEnvelope>;
  remove: (sessionId: string) => Promise<void>;
  download: (sessionId: string) => Promise<BrowserDownload>;
  save: (attachment: BrowserDownload) => void;
  navigateAfterDelete: () => void;
  publishDetail: (update: (current: MarginaliaSessionEnvelope) => MarginaliaSessionEnvelope) => void;
  publishFeedback: (kind: SessionDetailMutationKind, state: MutationState) => void;
  finishMetadataEdit: (field: MetadataField, value: string) => void;
}

const metadataKinds = new Set<SessionDetailMutationKind>(["name", "note"]);

export class MarginaliaSessionDetailMutationLifecycle {
  private sessionId: string | undefined;
  private lifetime = 0;
  private revision = 0;
  private lifecycleRevision = 0;
  private readonly active = new Map<SessionDetailMutationKind, SessionDetailMutationToken>();

  constructor(private readonly adapters: SessionDetailMutationAdapters) {}

  activate(sessionId: string): void {
    this.lifetime += 1;
    this.sessionId = sessionId;
    this.lifecycleRevision = 0;
    this.active.clear();
  }

  invalidate(sessionId: string): void {
    if (this.sessionId !== sessionId) return;
    this.lifetime += 1;
    this.sessionId = undefined;
    this.active.clear();
  }

  async saveMetadata(detail: MarginaliaSessionEnvelope, field: MetadataField, draft: string): Promise<void> {
    if (detail.session.status !== "active") return;
    const kind = field === "name" ? "name" : "note";
    const token = this.begin(detail.session.id, kind);
    if (!token) return;
    const value = draft.trim();
    const changed = value !== detail.session[field].trim();
    let result: MarginaliaSessionEnvelope;
    try {
      result = changed ? await this.adapters.update(detail.session.id, { [field]: value }) : detail;
    } catch (error: unknown) {
      this.fail(token, error);
      return;
    }
    if (!this.permitPublication(token)) return;
    if (changed) {
      // Metadata commands publish only their field, never an overlapping envelope.
      this.adapters.publishDetail((current) => current.session.id === result.session.id ? {
        ...current,
        session: { ...current.session, [field]: result.session[field] },
      } : current);
    }
    this.adapters.finishMetadataEdit(field, result.session[field]);
    this.adapters.publishFeedback(kind, changed
      ? { pending: false, message: `Reading Session ${kind} saved.` }
      : idleMutationState);
  }

  async closeSession(detail: MarginaliaSessionEnvelope): Promise<void> {
    if (detail.session.status !== "active") return;
    const token = this.begin(detail.session.id, "close");
    if (!token) return;
    let result: MarginaliaSessionEnvelope;
    try {
      result = await this.adapters.close(detail.session.id);
    } catch (error: unknown) {
      this.fail(token, error);
      return;
    }
    if (!this.permitPublication(token)) return;
    this.adapters.publishDetail((current) => current.session.id === token.sessionId ? result : current);
    this.adapters.publishFeedback("close", { pending: false, message: "Reading Session closed." });
  }

  async deleteSession(sessionId: string): Promise<void> {
    const token = this.begin(sessionId, "delete");
    if (!token) return;
    try {
      await this.adapters.remove(sessionId);
    } catch (error: unknown) {
      this.fail(token, error);
      return;
    }
    if (this.permitPublication(token)) this.adapters.navigateAfterDelete();
  }

  async exportSession(sessionId: string): Promise<void> {
    const token = this.begin(sessionId, "export");
    if (!token) return;
    let attachment: BrowserDownload;
    try {
      attachment = await this.adapters.download(sessionId);
    } catch (error: unknown) {
      this.fail(token, error);
      return;
    }
    // The browser effect must pass the same settlement check as state publication.
    if (!this.permitPublication(token)) return;
    try {
      this.adapters.save(attachment);
      this.adapters.publishFeedback("export", idleMutationState);
    } catch (error: unknown) {
      // Settlement already released the command; do not settle twice and lose
      // adapter failures as expired work.
      this.adapters.publishFeedback("export", { pending: false, error: normalizeMutationError(error) });
    }
  }

  private fail(token: SessionDetailMutationToken, error: unknown): void {
    if (this.permitPublication(token)) {
      this.adapters.publishFeedback(token.kind, { pending: false, error: normalizeMutationError(error) });
    }
  }

  private permitPublication(token: SessionDetailMutationToken): boolean {
    const settlement = this.settle(token);
    if (settlement === "discard") this.adapters.publishFeedback(token.kind, idleMutationState);
    return settlement === "publish";
  }

  private begin(sessionId: string, kind: SessionDetailMutationKind): SessionDetailMutationToken | undefined {
    if (sessionId !== this.sessionId || this.active.has(kind)) return undefined;
    if (metadataKinds.has(kind) && this.hasLifecycleMutation()) return undefined;
    if (kind === "close" && this.hasLifecycleMutation()) return undefined;
    if (kind === "delete" && (this.hasLifecycleMutation() || this.active.has("export"))) return undefined;
    if (kind === "export" && (this.active.has("delete") || this.active.has("export"))) return undefined;

    if (kind === "close" || kind === "delete") {
      this.lifecycleRevision += 1;
    }
    const token = {
      kind,
      sessionId,
      lifetime: this.lifetime,
      revision: ++this.revision,
      lifecycleRevision: this.lifecycleRevision,
    } satisfies SessionDetailMutationToken;
    this.active.set(kind, token);
    this.adapters.publishFeedback(kind, { pending: true });
    return token;
  }

  private settle(token: SessionDetailMutationToken): SessionDetailMutationSettlement {
    const active = this.active.get(token.kind);
    if (active?.revision !== token.revision) return "expired";
    this.active.delete(token.kind);
    if (this.sessionId !== token.sessionId || this.lifetime !== token.lifetime) return "expired";
    return this.lifecycleRevision === token.lifecycleRevision ? "publish" : "discard";
  }

  private hasLifecycleMutation(): boolean {
    return this.active.has("close") || this.active.has("delete");
  }
}

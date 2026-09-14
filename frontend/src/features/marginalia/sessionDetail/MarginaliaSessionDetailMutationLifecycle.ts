export type SessionDetailMutationKind = "name" | "note" | "close" | "delete" | "export";

export interface SessionDetailMutationToken {
  readonly kind: SessionDetailMutationKind;
  readonly sessionId: string;
  readonly lifetime: number;
  readonly revision: number;
  readonly lifecycleRevision: number;
}

export type SessionDetailMutationSettlement = "publish" | "discard" | "expired";

const metadataKinds = new Set<SessionDetailMutationKind>(["name", "note"]);

export class MarginaliaSessionDetailMutationLifecycle {
  private sessionId: string | undefined;
  private lifetime = 0;
  private revision = 0;
  private lifecycleRevision = 0;
  private readonly active = new Map<SessionDetailMutationKind, SessionDetailMutationToken>();

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

  begin(sessionId: string, kind: SessionDetailMutationKind): SessionDetailMutationToken | undefined {
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
    return token;
  }

  settle(token: SessionDetailMutationToken): SessionDetailMutationSettlement {
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

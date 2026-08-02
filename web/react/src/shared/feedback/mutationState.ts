export interface MutationState {
  pending: boolean;
  message?: string;
  error?: Error;
}

export class LocalValidationError extends Error {
  readonly fields?: Record<string, string[]>;

  constructor(message: string, fields?: Record<string, string[]>) {
    super(message);
    this.name = "LocalValidationError";
    this.fields = fields;
  }
}

export const idleMutationState: MutationState = { pending: false };

export function normalizeMutationError(error: unknown): Error {
  return error instanceof Error ? error : new Error("The request could not be completed.");
}

export function fieldError(error: Error | undefined, field: string): string | undefined {
  if (!error || !("fields" in error)) return undefined;
  const fields = (error as Error & { fields?: Record<string, string[]> }).fields;
  return fields?.[field]?.[0];
}

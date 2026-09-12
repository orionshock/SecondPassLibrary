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
  if (error instanceof Error) return error;
  console.error("Unexpected Product UI failure value.", { failureClass: typeof error });
  return new Error("The action couldn't be completed. Try again.");
}

export function fieldError(error: Error | undefined, field: string): string | undefined {
  if (!error || !("fields" in error)) return undefined;
  const fields = (error as Error & { fields?: Record<string, string[]> }).fields;
  return fields?.[field]?.[0];
}

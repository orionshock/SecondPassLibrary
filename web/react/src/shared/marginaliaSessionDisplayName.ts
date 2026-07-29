export function marginaliaSessionDisplayName(session: { id: string; name: string }): string {
  return session.name || `Unnamed Session ${session.id.slice(-6)}`;
}

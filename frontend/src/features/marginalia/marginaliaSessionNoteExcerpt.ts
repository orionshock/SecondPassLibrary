const SESSION_NOTE_EXCERPT_LENGTH = 120;

export function marginaliaSessionNoteExcerpt(note: string): string | undefined {
  const collapsed = note.replace(/\s+/g, " ").trim();
  if (!collapsed) return undefined;
  return collapsed.length > SESSION_NOTE_EXCERPT_LENGTH
    ? `${collapsed.slice(0, SESSION_NOTE_EXCERPT_LENGTH)}…`
    : collapsed;
}

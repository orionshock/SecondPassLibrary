export function buildReadingClientBookUrl(baseUrl: string, bookId: string): string {
  const normalizedBaseUrl = baseUrl.trim().replace(/\/+$/, "");
  if (/[{}]/.test(normalizedBaseUrl)) throw new Error("Reading Client URL cannot contain templates.");
  const parsed = new URL(normalizedBaseUrl);
  if (!["http:", "https:"].includes(parsed.protocol)
    || parsed.username
    || parsed.password
    || (parsed.pathname !== "/" && parsed.pathname !== "")
    || parsed.search
    || parsed.hash) {
    throw new Error("Reading Client URL must be an HTTP(S) root URL.");
  }
  return `${normalizedBaseUrl}/#/reader/${encodeURIComponent(bookId)}`;
}

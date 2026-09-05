export function buildSecondPassReaderBookUrl(baseUrl: string, bookId: string): string {
  const normalizedBaseUrl = baseUrl.trim().replace(/\/+$/, "");
  if (/[{}]/.test(normalizedBaseUrl)) throw new Error("Second Pass Reader Web Client URL cannot contain templates.");
  const parsed = new URL(normalizedBaseUrl);
  if (!["http:", "https:"].includes(parsed.protocol)
    || parsed.username
    || parsed.password
    || (parsed.pathname !== "/" && parsed.pathname !== "")
    || parsed.search
    || parsed.hash) {
    throw new Error("Second Pass Reader Web Client URL must be a canonical HTTP(S) base URL.");
  }
  return `${normalizedBaseUrl}/#/reader/${encodeURIComponent(bookId)}`;
}

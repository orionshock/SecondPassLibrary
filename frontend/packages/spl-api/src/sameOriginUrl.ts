export function sameOriginUrl(value: string): string {
  try {
    const url = new URL(value, "http://second-pass.invalid");
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return value;
  }
}

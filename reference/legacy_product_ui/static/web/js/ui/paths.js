export function productUiPath(path) {
  const normalized = String(path || "/").startsWith("/") ? String(path || "/") : `/${path}`;
  const prefix = document.body && document.body.dataset ? String(document.body.dataset.productUiPrefix || "") : "";
  return `${prefix}${normalized}`;
}

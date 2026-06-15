export function resolveStatusTarget(target) {
  if (!target) return null;
  if (typeof target === "string") return document.querySelector(target);
  return target;
}

export function setStatus(target, message, options = {}) {
  const el = resolveStatusTarget(target);
  if (!el) return;
  const isError = typeof options === "boolean" ? options : !!options.isError;
  const errorClass = typeof options === "object" && options.errorClass ? options.errorClass : "error";
  el.textContent = message || "";
  el.classList.toggle(errorClass, isError);
}

export function clearStatus(target, options = {}) {
  const statusOptions = typeof options === "boolean" ? { isError: false } : { ...options, isError: false };
  setStatus(target, "", statusOptions);
}

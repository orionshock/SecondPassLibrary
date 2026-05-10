export function getCookie(name) {
  const cookies = document.cookie ? document.cookie.split(";") : [];
  for (const cookie of cookies) {
    const trimmed = cookie.trim();
    if (!trimmed) continue;
    if (trimmed.startsWith(name + "=")) {
      return decodeURIComponent(trimmed.slice(name.length + 1));
    }
  }
  return null;
}

export function getCsrfToken() {
  return getCookie("csrftoken");
}

export async function fetchJSON(url) {
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });

  const contentType = (response.headers.get("content-type") || "").toLowerCase();
  const isJson = contentType.includes("application/json");

  let bodyText = "";
  let bodyJson = null;

  if (isJson) {
    try {
      bodyJson = await response.json();
    } catch (e) {
      console.error("Failed to parse JSON response", { url, status: response.status, e });
      throw new Error(`Invalid JSON response (${response.status}).`);
    }
  } else {
    bodyText = await response.text().catch(() => "");
  }

  if (!response.ok) {
    const snippet = (bodyText || "").trim().slice(0, 160);
    const error = new Error(
      snippet ? `Request failed (${response.status}): ${snippet}` : `Request failed (${response.status}).`
    );
    error.status = response.status;
    error.body = isJson ? bodyJson : bodyText;
    throw error;
  }

  if (!isJson) {
    const snippet = (bodyText || "").trim().slice(0, 160);
    throw new Error(
      snippet ? `Expected JSON but received: ${snippet}` : "Expected JSON but received non-JSON response."
    );
  }

  return bodyJson;
}

export async function fetchJSONWithOptions(url, options) {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
  });

  const contentType = (response.headers.get("content-type") || "").toLowerCase();
  const isJson = contentType.includes("application/json");

  let bodyText = "";
  let bodyJson = null;

  if (isJson) {
    try {
      bodyJson = await response.json();
    } catch (e) {
      console.error("Failed to parse JSON response", { url, status: response.status, e });
      throw new Error(`Invalid JSON response (${response.status}).`);
    }
  } else {
    bodyText = await response.text().catch(() => "");
  }

  if (!response.ok) {
    const snippet = (bodyText || "").trim().slice(0, 160);
    const error = new Error(
      snippet ? `Request failed (${response.status}): ${snippet}` : `Request failed (${response.status}).`
    );
    error.status = response.status;
    error.body = isJson ? bodyJson : bodyText;
    throw error;
  }

  return isJson ? bodyJson : bodyText;
}

export function extractApiErrorMessage(error) {
  const body = error && error.body ? error.body : null;
  if (body && typeof body === "object") {
    if (body.error && typeof body.error === "object") {
      const code = body.error.code ? String(body.error.code) : "";
      const msg = body.error.message ? String(body.error.message) : "";
      if (code && msg) return `${code}: ${msg}`;
      if (msg) return msg;
      if (code) return code;
    }
    if (body.detail) return String(body.detail);
  }
  return error && error.message ? String(error.message) : "Unknown error.";
}

export function summarizeFieldErrors(body) {
  if (!body || typeof body !== "object") return "";
  const entries = Object.entries(body)
    .filter(([k]) => k !== "error" && k !== "detail")
    .slice(0, 8)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`);
  return entries.length ? entries.join(" | ") : "";
}


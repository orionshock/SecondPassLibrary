import {
  extractApiErrorMessage,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
} from "../api.js";
import { $, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { setStatus } from "./shared.js";

export async function initShelfNew() {
  await loadMeAndInitShell();
  setGlobalError("");

  const statusEl = $("#shelf-new-status");
  const cardEl = $("#shelf-new-card");
  const errEl = $("#shelf-new-error");
  const formEl = $("#shelf-new-form");
  const nameEl = $("#shelf-new-name");
  const descEl = $("#shelf-new-description");
  const ownerTypeEl = $("#shelf-new-owner-type");
  const visibilityEl = $("#shelf-new-visibility");
  const ownerGroupEl = $("#shelf-new-owner-group");
  const submitStatusEl = $("#shelf-new-submit-status");
  if (!statusEl || !cardEl || !errEl || !formEl || !nameEl || !descEl || !ownerTypeEl || !visibilityEl || !ownerGroupEl) return;

  function setErr(msg) {
    errEl.textContent = msg || "";
    visible(errEl, !!msg);
  }

  setStatus(statusEl, "Loadingâ€¦", false);
  setErr("");
  visible(cardEl, true);

  const groups = await fetchJSON("/api/v1/library/groups/");
  const results = Array.isArray(groups && groups.results) ? groups.results : [];
  ownerGroupEl.textContent = "";
  for (const g of results) {
    const opt = document.createElement("option");
    opt.value = String(g.id);
    opt.textContent = String(g.name || g.id);
    ownerGroupEl.appendChild(opt);
  }

  const qs = new URLSearchParams(window.location.search || "");
  const preOwnerType = qs.get("owner_type");
  const preOwnerGroup = qs.get("owner_group");
  if (preOwnerType === "group") ownerTypeEl.value = "group";
  else if (preOwnerGroup) ownerTypeEl.value = "group";
  if (preOwnerGroup) ownerGroupEl.value = preOwnerGroup;

  function syncOwnerUI() {
    const isGroup = ownerTypeEl.value === "group";
    visibilityEl.disabled = isGroup;
    ownerGroupEl.disabled = !isGroup;
    if (isGroup) visibilityEl.value = "private";
  }
  ownerTypeEl.addEventListener("change", syncOwnerUI);
  syncOwnerUI();

  setStatus(statusEl, "", false);

  formEl.addEventListener("submit", async (e) => {
    e.preventDefault();
    setGlobalError("");
    setErr("");
    setStatus(submitStatusEl, "Creatingâ€¦", false);

    const body = {
      name: nameEl.value || "",
      description: descEl.value || "",
      owner_type: ownerTypeEl.value,
    };
    if (ownerTypeEl.value === "user") body.visibility = visibilityEl.value;
    if (ownerTypeEl.value === "group") body.owner_group = ownerGroupEl.value;

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const created = await fetchJSONWithOptions("/api/v1/shelves/", {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });

      setStatus(submitStatusEl, "", false);
      const id = created && created.id ? String(created.id) : "";
      window.location.href = id ? `/shelves/${encodeURIComponent(id)}/edit/` : "/shelves/";
    } catch (e2) {
      console.error("Failed to create shelf", e2);
      const msg = extractApiErrorMessage(e2);
      setErr(msg);
      setGlobalError(msg);
      setStatus(submitStatusEl, "", true);
    }
  });
}


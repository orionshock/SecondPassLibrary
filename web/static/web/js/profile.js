import { getCsrfToken, fetchJSONWithOptions, extractApiErrorMessage } from "./api.js";
import { $, escapeHtml, formatRole, loadMeAndInitShell, setGlobalError, setText } from "./layout.js";

function renderGroups(groups) {
  if (!Array.isArray(groups) || groups.length === 0) {
    return '<div class="muted">No group memberships.</div>';
  }
  const items = groups
    .map((g) => {
      const bits = [];
      if (g.is_public_group) bits.push("Public");
      if (g.membership_role) bits.push(g.membership_role);
      return `<li><span>${escapeHtml(g.name)}</span> <span class="muted">(${escapeHtml(bits.join(", ") || "member")})</span></li>`;
    })
    .join("");
  return `<ul>${items}</ul>`;
}

function renderCapabilities(caps) {
  const entries = caps && typeof caps === "object" ? Object.entries(caps) : [];
  if (entries.length === 0) return '<div class="muted">No capabilities.</div>';
  const items = entries
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([k, v]) => `<li><code>${escapeHtml(k)}</code>: ${v ? "yes" : "no"}</li>`)
    .join("");
  return `<ul>${items}</ul>`;
}

export async function initProfile() {
  const me = await loadMeAndInitShell();
  if (!me) {
    setText($("#profile-summary"), "Error loading identity.");
    setText($("#profile-edit-status"), "Error loading identity.");
    setText($("#profile-groups"), "Error loading identity.");
    setText($("#profile-capabilities"), "Error loading identity.");
    return;
  }

  const ownerBadge = me.is_owner ? ' <span class="pill pill--owner">Owner</span>' : "";
  $("#profile-summary").innerHTML = `
      <div class="kv">
        <div class="kv__k">Username</div><div class="kv__v">${escapeHtml(me.username || "")}${ownerBadge}</div>
        <div class="kv__k">Role</div><div class="kv__v">${escapeHtml(formatRole(me.role))}</div>
        <div class="kv__k">Email</div><div class="kv__v" id="profile-email">${escapeHtml(me.email || "")}</div>
        <div class="kv__k">First name</div><div class="kv__v" id="profile-first">${escapeHtml(me.first_name || "")}</div>
        <div class="kv__k">Last name</div><div class="kv__v" id="profile-last">${escapeHtml(me.last_name || "")}</div>
      </div>
    `.trim();

  $("#profile-groups").innerHTML = renderGroups(me.groups);
  $("#profile-capabilities").innerHTML = renderCapabilities(me.capabilities);

  const form = $("#profile-edit-form");
  const emailInput = $("#profile-edit-email");
  const firstInput = $("#profile-edit-first");
  const lastInput = $("#profile-edit-last");
  const statusEl = $("#profile-edit-status");

  if (!form || !emailInput || !firstInput || !lastInput || !statusEl) return;

  emailInput.value = me.email || "";
  firstInput.value = me.first_name || "";
  lastInput.value = me.last_name || "";

  statusEl.textContent = "";
  statusEl.classList.remove("error");

  if (form.dataset.bound) return;
  form.dataset.bound = "1";
  form.dataset.baseEmail = emailInput.value || "";
  form.dataset.baseFirst = firstInput.value || "";
  form.dataset.baseLast = lastInput.value || "";

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setGlobalError("");
    statusEl.textContent = "Saving…";
    statusEl.classList.remove("error");

    const desired = {
      email: (emailInput.value || "").trim(),
      first_name: (firstInput.value || "").trim(),
      last_name: (lastInput.value || "").trim(),
    };

    const patch = {};
    if (String(desired.email) !== String(form.dataset.baseEmail || "")) patch.email = desired.email;
    if (String(desired.first_name) !== String(form.dataset.baseFirst || "")) patch.first_name = desired.first_name;
    if (String(desired.last_name) !== String(form.dataset.baseLast || "")) patch.last_name = desired.last_name;

    if (Object.keys(patch).length === 0) {
      statusEl.textContent = "No changes.";
      return;
    }

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const updated = await fetchJSONWithOptions("/api/v1/accounts/me/", {
        method: "PATCH",
        headers,
        body: JSON.stringify(patch),
      });

      statusEl.textContent = "Saved.";
      form.dataset.baseEmail = desired.email;
      form.dataset.baseFirst = desired.first_name;
      form.dataset.baseLast = desired.last_name;

      const emailEl = $("#profile-email");
      if (emailEl) emailEl.textContent = desired.email;
      const firstEl = $("#profile-first");
      if (firstEl) firstEl.textContent = desired.first_name;
      const lastEl = $("#profile-last");
      if (lastEl) lastEl.textContent = desired.last_name;

      // Keep local me-ish fields in sync if we got a payload back.
      if (updated && typeof updated === "object") {
        me.email = updated.email;
        me.first_name = updated.first_name;
        me.last_name = updated.last_name;
      }
    } catch (e2) {
      console.error("Failed to save /api/v1/accounts/me/", e2);
      const msg = extractApiErrorMessage(e2);
      statusEl.textContent = msg;
      statusEl.classList.add("error");
      setGlobalError(msg);
    }
  });
}


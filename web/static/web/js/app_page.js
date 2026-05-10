import { getCsrfToken, fetchJSONWithOptions, extractApiErrorMessage } from "./api.js";
import {
  $,
  escapeHtml,
  formatRole,
  loadMeAndInitShell,
  setGlobalError,
  setText,
} from "./layout.js";

function renderGroups(groups) {
  if (!Array.isArray(groups) || groups.length === 0) {
    return '<div class="muted">No group memberships.</div>';
  }
  const items = groups
    .map((g) => {
      const bits = [];
      if (g.is_public_group) bits.push("Public");
      if (g.membership_role) bits.push(g.membership_role);
      return `<li><span>${escapeHtml(g.name)}</span> <span class="muted">(${escapeHtml(
        bits.join(", ") || "member"
      )})</span></li>`;
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

function navShouldShowGroups(me) {
  if (!me) return false;
  const groups = Array.isArray(me.groups) ? me.groups : [];
  const caps = me.capabilities || {};
  return (
    groups.length > 0 ||
    !!caps.can_manage_library ||
    !!caps.can_create_library_groups ||
    !!caps.can_manage_group_memberships ||
    !!caps.can_manage_group_identity ||
    !!caps.can_edit_group_presentation
  );
}

function navShouldShowAdmin(me) {
  if (!me) return false;
  if (me.is_owner) return true;
  return me.role === "manager";
}

function sectionLinksForMe(me) {
  const caps = me && me.capabilities ? me.capabilities : {};
  const sections = [{ href: "/library/", label: "Library", visible: true }];
  sections.push({ href: "/groups/", label: "Groups", visible: navShouldShowGroups(me) });
  sections.push({ href: "/imports/", label: "Imports", visible: !!caps.can_access_imports });
  sections.push({ href: "/users/", label: "Users", visible: !!caps.can_manage_users });
  sections.push({ href: "/admin/", label: "Service Hatch", visible: navShouldShowAdmin(me) });
  return sections.filter((s) => s.visible);
}

export async function initDashboard() {
  const me = await loadMeAndInitShell();
  if (!me) {
    setText($("#me-summary"), "Error loading identity.");
    setText($("#me-edit-status"), "Error loading identity.");
    setText($("#me-groups"), "Error loading identity.");
    setText($("#me-capabilities"), "Error loading identity.");
    setText($("#me-sections"), "Error loading identity.");
    return;
  }

  const ownerBadge = me.is_owner ? ' <span class="pill pill--owner">Owner</span>' : "";
  $("#me-summary").innerHTML = `
      <div class="kv">
        <div class="kv__k">Username</div><div class="kv__v">${escapeHtml(me.username || "")}${ownerBadge}</div>
        <div class="kv__k">Role</div><div class="kv__v">${escapeHtml(formatRole(me.role))}</div>
        <div class="kv__k">Email</div><div class="kv__v" id="me-email">${escapeHtml(me.email || "")}</div>
      </div>
    `.trim();

  $("#me-groups").innerHTML = renderGroups(me.groups);
  $("#me-capabilities").innerHTML = renderCapabilities(me.capabilities);

  const sections = sectionLinksForMe(me)
    .map((s) => `<a class="button" href="${escapeHtml(s.href)}">${escapeHtml(s.label)}</a>`)
    .join(" ");
  $("#me-sections").innerHTML = sections || '<div class="muted">No sections.</div>';

  const form = $("#me-edit-form");
  const emailInput = $("#me-edit-email");
  const firstInput = $("#me-edit-first");
  const lastInput = $("#me-edit-last");
  const statusEl = $("#me-edit-status");

  if (form && emailInput && firstInput && lastInput && statusEl) {
    // Email comes from /me/ payload; names are server-rendered in the template.
    emailInput.value = me.email || "";
    statusEl.textContent = "";
    statusEl.classList.remove("error");

    if (!form.dataset.bound) {
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

          await fetchJSONWithOptions("/api/v1/accounts/me/", {
            method: "PATCH",
            headers,
            body: JSON.stringify(patch),
          });

          statusEl.textContent = "Saved.";
          form.dataset.baseEmail = desired.email;
          form.dataset.baseFirst = desired.first_name;
          form.dataset.baseLast = desired.last_name;
          const emailEl = $("#me-email");
          if (emailEl) emailEl.textContent = desired.email;
        } catch (e2) {
          console.error("Failed to save /api/v1/accounts/me/", e2);
          const msg = extractApiErrorMessage(e2);
          statusEl.textContent = msg;
          statusEl.classList.add("error");
          setGlobalError(msg);
        }
      });
    }
  }
}


import { getCsrfToken, fetchJSONWithOptions, extractApiErrorMessage } from "../api.js";
import { $, loadMeAndInitShell, setGlobalError, setText, visible } from "../layout.js";
import { renderGroupBadge } from "../ui/groups.js";
import { renderUserIdentity } from "../ui/identity.js";

function clear(node) {
  if (!node) return;
  while (node.firstChild) node.removeChild(node.firstChild);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function renderGroups(container, groups) {
  clear(container);
  if (!Array.isArray(groups) || groups.length === 0) {
    container.appendChild(el("div", "muted", "No group memberships."));
    return;
  }
  const ul = document.createElement("ul");
  for (const g of groups) {
    const li = document.createElement("li");
    li.appendChild(renderGroupBadge(g, { compact: true }));
    const bits = [];
    bits.push("Member");
    if (g && g.is_curator) bits.push("Curator");
    li.appendChild(document.createTextNode(" "));
    li.appendChild(el("span", "muted", `(${bits.join(", ")})`));
    ul.appendChild(li);
  }
  container.appendChild(ul);
}

function renderAccess(container, me) {
  clear(container);
  const ul = document.createElement("ul");
  const role = me && me.role ? String(me.role) : "reader";
  const rows = [
    ["Global role", role],
    ["Owner", me && me.is_owner ? "yes" : "no"],
  ];
  for (const [label, value] of rows) {
    const li = document.createElement("li");
    li.appendChild(document.createTextNode(`${label}: ${value}`));
    ul.appendChild(li);
  }
  container.appendChild(ul);
}

function formatWhen(value) {
  if (!value) return "";
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString();
}

function renderClientSessions(container, sessions, onRevoke) {
  clear(container);
  if (!Array.isArray(sessions) || sessions.length === 0) {
    container.appendChild(el("div", "muted", "No device/API sessions connected."));
    return;
  }

  const table = document.createElement("table");
  table.className = "table";
  const thead = document.createElement("thead");
  thead.innerHTML = `<tr>
    <th>Device/client name</th>
    <th class="muted">Type</th>
    <th class="muted">Last seen</th>
    <th></th>
  </tr>`;
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const s of sessions) {
    const tr = document.createElement("tr");

    const name = s && s.name ? String(s.name) : "";
    const ctype = s && s.client_type ? String(s.client_type) : "";
    const when = formatWhen((s && (s.last_seen_at || s.created_at)) || "");

    const tdName = document.createElement("td");
    tdName.textContent = name;
    tr.appendChild(tdName);

    const tdType = document.createElement("td");
    tdType.className = "muted";
    tdType.textContent = ctype;
    tr.appendChild(tdType);

    const tdWhen = document.createElement("td");
    tdWhen.className = "muted";
    tdWhen.textContent = when;
    tr.appendChild(tdWhen);

    const tdBtn = document.createElement("td");
    const btn = el("button", "button", "Revoke");
    btn.type = "button";
    btn.addEventListener("click", () => onRevoke(s));
    tdBtn.appendChild(btn);
    tr.appendChild(tdBtn);

    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  container.appendChild(table);
}

export async function initProfile() {
  const me = await loadMeAndInitShell();
  const groupsEl = $("#profile-groups");
  const accessEl = $("#profile-access");
  const statusEl = $("#profile-edit-status");

  if (!me) {
    setText(statusEl, "Error loading identity.");
    setText(groupsEl, "Error loading identity.");
    setText(accessEl, "Error loading identity.");
    return;
  }

  renderGroups(groupsEl, me.groups);
  renderAccess(accessEl, me);

  const form = $("#profile-edit-form");
  const editBtn = $("#profile-edit-btn");
  const saveBtn = $("#profile-save-btn");
  const cancelBtn = $("#profile-cancel-btn");

  const usernameEl = $("#profile-username");
  const emailDisplayEl = $("#profile-email-display");
  const firstDisplayEl = $("#profile-first-display");
  const lastDisplayEl = $("#profile-last-display");

  const emailInput = $("#profile-email-input");
  const firstInput = $("#profile-first-input");
  const lastInput = $("#profile-last-input");

  if (
    !form ||
    !editBtn ||
    !saveBtn ||
    !cancelBtn ||
    !statusEl ||
    !usernameEl ||
    !emailDisplayEl ||
    !firstDisplayEl ||
    !lastDisplayEl ||
    !emailInput ||
    !firstInput ||
    !lastInput
  ) {
    return;
  }

  function setEditing(on) {
    visible(editBtn, !on);
    visible(saveBtn, on);
    visible(cancelBtn, on);

    visible(emailDisplayEl, !on);
    visible(firstDisplayEl, !on);
    visible(lastDisplayEl, !on);

    visible(emailInput, on);
    visible(firstInput, on);
    visible(lastInput, on);

    if (on) emailInput.focus();
  }

  function setBaseFromMe() {
    form.dataset.baseEmail = me.email || "";
    form.dataset.baseFirst = me.first_name || "";
    form.dataset.baseLast = me.last_name || "";
  }

  function syncDisplayFromMe() {
    usernameEl.replaceChildren(renderUserIdentity(me));
    emailDisplayEl.textContent = me.email || "";
    firstDisplayEl.textContent = me.first_name || "";
    lastDisplayEl.textContent = me.last_name || "";
  }

  function syncInputsFromBase() {
    emailInput.value = form.dataset.baseEmail || "";
    firstInput.value = form.dataset.baseFirst || "";
    lastInput.value = form.dataset.baseLast || "";
  }

  statusEl.textContent = "";
  statusEl.classList.remove("error");

  syncDisplayFromMe();
  setBaseFromMe();
  syncInputsFromBase();
  setEditing(false);

  if (!form.dataset.bound) {
    form.dataset.bound = "1";

    editBtn.addEventListener("click", () => {
      statusEl.textContent = "";
      statusEl.classList.remove("error");
      syncInputsFromBase();
      setEditing(true);
    });

    cancelBtn.addEventListener("click", () => {
      statusEl.textContent = "";
      statusEl.classList.remove("error");
      syncInputsFromBase();
      setEditing(false);
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      setGlobalError("");
      statusEl.textContent = "Saving...";
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
        setEditing(false);
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

        if (updated && typeof updated === "object") {
          me.email = updated.email;
          me.first_name = updated.first_name;
          me.last_name = updated.last_name;
        } else {
          me.email = desired.email;
          me.first_name = desired.first_name;
          me.last_name = desired.last_name;
        }

        syncDisplayFromMe();
        setBaseFromMe();
        syncInputsFromBase();
        statusEl.textContent = "Saved.";
        setEditing(false);
      } catch (e2) {
        console.error("Failed to save /api/v1/accounts/me/", e2);
        const msg = extractApiErrorMessage(e2);
        statusEl.textContent = msg;
        statusEl.classList.add("error");
        setGlobalError(msg);
      }
    });
  }

  const logoutOthersBtn = $("#profile-logout-others-btn");
  const logoutOthersStatusEl = $("#profile-logout-others-status");
  if (logoutOthersBtn && logoutOthersStatusEl && !logoutOthersBtn.dataset.bound) {
    logoutOthersBtn.dataset.bound = "1";

    logoutOthersBtn.addEventListener("click", async () => {
      setGlobalError("");
      logoutOthersStatusEl.textContent = "Working...";
      logoutOthersStatusEl.classList.remove("error");
      logoutOthersBtn.disabled = true;

      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions("/api/v1/accounts/me/web-sessions/logout-others/", {
          method: "POST",
          headers,
          body: JSON.stringify({}),
        });

        logoutOthersStatusEl.textContent = "Other web sessions logged out.";
      } catch (e2) {
        console.error("Failed to log out other web sessions", e2);
        const msg = extractApiErrorMessage(e2);
        logoutOthersStatusEl.textContent = msg;
        logoutOthersStatusEl.classList.add("error");
        setGlobalError(msg);
      } finally {
        logoutOthersBtn.disabled = false;
      }
    });
  }

  const clientSessionsEl = $("#profile-client-sessions");
  const clientSessionsStatusEl = $("#profile-client-sessions-status");
  if (clientSessionsEl && clientSessionsStatusEl) {
    async function loadClientSessions() {
      try {
        clientSessionsStatusEl.textContent = "";
        clientSessionsStatusEl.classList.remove("error");
        const sessions = await fetchJSONWithOptions("/api/v1/accounts/me/client-sessions/", {
          method: "GET",
          headers: { Accept: "application/json" },
        });
        renderClientSessions(clientSessionsEl, sessions, revokeClientSession);
      } catch (e2) {
        console.error("Failed to load client sessions", e2);
        const msg = extractApiErrorMessage(e2);
        clientSessionsEl.textContent = "Error loading device/API sessions.";
        clientSessionsStatusEl.textContent = msg;
        clientSessionsStatusEl.classList.add("error");
        setGlobalError(msg);
      }
    }

    async function revokeClientSession(session) {
      const id = session && session.id ? String(session.id) : "";
      const name = session && session.name ? String(session.name) : "this session";
      if (!id) return;
      if (!window.confirm(`Revoke ${name}? This will invalidate its bearer token.`)) return;

      clientSessionsStatusEl.textContent = "Revoking...";
      clientSessionsStatusEl.classList.remove("error");
      setGlobalError("");

      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(`/api/v1/accounts/me/client-sessions/${encodeURIComponent(id)}/`, {
          method: "DELETE",
          headers,
        });

        clientSessionsStatusEl.textContent = "Revoked.";
        await loadClientSessions();
      } catch (e2) {
        console.error("Failed to revoke client session", e2);
        const msg = extractApiErrorMessage(e2);
        clientSessionsStatusEl.textContent = msg;
        clientSessionsStatusEl.classList.add("error");
        setGlobalError(msg);
      }
    }

    await loadClientSessions();
  }
}

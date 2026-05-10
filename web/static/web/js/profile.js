import { getCsrfToken, fetchJSONWithOptions, extractApiErrorMessage } from "./api.js";
import { $, formatRole, loadMeAndInitShell, setGlobalError, setText, visible } from "./layout.js";

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
    const name = g && g.name ? String(g.name) : "";
    li.appendChild(el("span", "", name));
    const bits = [];
    if (g && g.is_public_group) bits.push("Public");
    if (g && g.membership_role) bits.push(String(g.membership_role));
    li.appendChild(document.createTextNode(" "));
    li.appendChild(el("span", "muted", `(${bits.join(", ") || "member"})`));
    ul.appendChild(li);
  }
  container.appendChild(ul);
}

function renderCapabilities(container, caps) {
  clear(container);
  const entries = caps && typeof caps === "object" ? Object.entries(caps) : [];
  if (entries.length === 0) {
    container.appendChild(el("div", "muted", "No capabilities."));
    return;
  }
  const ul = document.createElement("ul");
  for (const [k, v] of entries.sort((a, b) => a[0].localeCompare(b[0]))) {
    const li = document.createElement("li");
    const code = document.createElement("code");
    code.textContent = String(k);
    li.appendChild(code);
    li.appendChild(document.createTextNode(`: ${v ? "yes" : "no"}`));
    ul.appendChild(li);
  }
  container.appendChild(ul);
}

function renderSummary(container, me) {
  clear(container);
  const kv = el("div", "kv");
  function addRow(k, vNodeOrText) {
    kv.appendChild(el("div", "kv__k", k));
    const v = el("div", "kv__v");
    if (vNodeOrText && vNodeOrText.nodeType) v.appendChild(vNodeOrText);
    else v.textContent = vNodeOrText != null ? String(vNodeOrText) : "";
    kv.appendChild(v);
  }

  const usernameWrap = document.createElement("span");
  usernameWrap.textContent = me.username || "";
  if (me.is_owner) {
    usernameWrap.appendChild(document.createTextNode(" "));
    usernameWrap.appendChild(el("span", "pill pill--owner", "Owner"));
  }

  addRow("Username", usernameWrap);
  addRow("Role", formatRole(me.role));

  const email = el("div", "", me.email || "");
  email.id = "profile-email";
  addRow("Email", email);
  const first = el("div", "", me.first_name || "");
  first.id = "profile-first";
  addRow("First name", first);
  const last = el("div", "", me.last_name || "");
  last.id = "profile-last";
  addRow("Last name", last);

  container.appendChild(kv);
}

export async function initProfile() {
  const me = await loadMeAndInitShell();
  const summaryEl = $("#profile-summary");
  const groupsEl = $("#profile-groups");
  const capsEl = $("#profile-capabilities");
  const statusEl = $("#profile-edit-status");

  if (!me) {
    setText(summaryEl, "Error loading identity.");
    setText(statusEl, "Error loading identity.");
    setText(groupsEl, "Error loading identity.");
    setText(capsEl, "Error loading identity.");
    return;
  }

  renderSummary(summaryEl, me);
  renderGroups(groupsEl, me.groups);
  renderCapabilities(capsEl, me.capabilities);

  const form = $("#profile-edit-form");
  const emailInput = $("#profile-edit-email");
  const firstInput = $("#profile-edit-first");
  const lastInput = $("#profile-edit-last");

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


import { fetchJSON } from "./api.js";
import { $, loadMeAndInitShell, setText, visible } from "./layout.js";

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

function formatWhen(value) {
  if (!value) return "";
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function renderRecentItem(item) {
  const wrap = el("a", "recent-reading__item", "");
  const bookId = item && item.book && item.book.id ? String(item.book.id) : "";
  const sessionId = item && item.session && item.session.id ? String(item.session.id) : "";
  wrap.setAttribute(
    "href",
    sessionId
      ? `/reading/sessions/books/${encodeURIComponent(bookId)}/${encodeURIComponent(sessionId)}/`
      : `/reading/sessions/books/${encodeURIComponent(bookId)}/`,
  );

  const titleText = item.book && item.book.title ? String(item.book.title) : "";
  const cover = el("div", "recent-reading__cover", "");
  const coverUrl = item.book && item.book.cover_url ? String(item.book.cover_url) : "";
  if (coverUrl) {
    const img = document.createElement("img");
    img.className = "recent-reading__cover-img";
    img.alt = titleText || "Cover";
    img.loading = "lazy";
    img.src = coverUrl;
    cover.appendChild(img);
  } else {
    cover.textContent = "Cover";
    cover.setAttribute("aria-hidden", "true");
  }

  const progression = item && item.session ? item.session.progression : null;
  const p = progression != null ? Number(progression) : null;
  if (p != null && Number.isFinite(p)) {
    const percent = Math.max(0, Math.min(100, Math.round(p * 100)));
    const badge = el("div", "recent-reading__progress", `${percent}%`);
    cover.appendChild(badge);
  }
  wrap.appendChild(cover);

  const meta = el("div", "recent-reading__meta", "");
  const title = el(
    "div",
    "recent-reading__title",
    titleText,
  );
  const when = el(
    "div",
    "muted recent-reading__when",
    formatWhen(item.last_activity_at),
  );
  meta.appendChild(title);
  meta.appendChild(when);

  const sessionName = item && item.session && item.session.name ? String(item.session.name).trim() : "";
  if (sessionName) {
    wrap.title = `${sessionName}`;
  }

  const allSessions = el("a", "muted", "[All Sessions]");
  allSessions.href = `/reading/sessions/books/${encodeURIComponent(bookId)}/`;
  allSessions.addEventListener("click", (e) => {
    e.stopPropagation();
  });
  meta.appendChild(allSessions);

  wrap.appendChild(meta);

  if (item.session && item.session.id) {
    wrap.dataset.sessionId = String(item.session.id);
  }

  return wrap;
}

export async function initDashboard() {
  const me = await loadMeAndInitShell();
  const recentStatusEl = $("#recent-reading-status");
  const recentListEl = $("#recent-reading-list");
  if (!recentStatusEl || !recentListEl) return;

  if (!me) {
    setText(recentStatusEl, "Could not load recent reading activity.");
    return;
  }

  async function loadRecent() {
    setText(recentStatusEl, "Loading...");
    clear(recentListEl);
    visible(recentListEl, false);

    try {
      const data = await fetchJSON("/api/v1/reading/sessions/recent/?limit=10");
      const results = data && Array.isArray(data.results) ? data.results : [];
      if (!results.length) {
        setText(recentStatusEl, "No recent reading activity yet.");
        return;
      }

      setText(recentStatusEl, "");
      visible(recentListEl, true);
      for (const item of results.slice(0, 10)) {
        if (!item || !item.book || !item.book.id) continue;
        recentListEl.appendChild(renderRecentItem(item));
      }
    } catch (e) {
      console.error("Failed to load recent reading activity", e);
      setText(recentStatusEl, "Could not load recent reading activity.");
    }
  }

  await loadRecent();
}

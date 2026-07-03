function clear(el) {
  if (!el) return;
  while (el.firstChild) el.removeChild(el.firstChild);
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

export function renderBookMeta(container, book) {
  clear(container);
  const canOpen = !(book && book.can_open === false);
  const title = book && book.title ? String(book.title) : "Book unavailable";
  const bookId = book && book.id ? String(book.id) : "";
  const subtitle = book && book.subtitle ? String(book.subtitle) : "";
  const authorObjects = Array.isArray(book && book.authors) ? book.authors.filter(Boolean) : [];
  const authors = authorObjects.map((a) => a && a.name).filter(Boolean);
  const series = book && book.series && book.series.name ? String(book.series.name) : "";
  const seriesId = book && book.series && book.series.id ? String(book.series.id) : "";
  const seriesIndex = book && book.series_index != null && book.series_index !== "" ? String(book.series_index) : "";

  const wrap = document.createElement("div");
  wrap.className = "book-meta";

  wrap.appendChild(
    contextRow(
      el("div", "book-meta__line", title),
      canOpen && bookId
        ? contextAction(
            `/library/books/${encodeURIComponent(bookId)}/`,
            "View book in Library",
            `View ${title} in Library`,
          )
        : null,
    )
  );
  if (subtitle) wrap.appendChild(el("div", "muted", subtitle));
  if (authors.length) {
    const primaryAuthor = authorObjects.find((author) => author && author.id && author.name);
    wrap.appendChild(
      contextRow(
        el("div", "book-meta__line", authors.join(", ")),
        canOpen && primaryAuthor
          ? contextAction(`/library/?view=author&author=${encodeURIComponent(String(primaryAuthor.id))}`, "View author in Library", `View ${primaryAuthor.name} in Library`)
          : null,
      )
    );
  }
  if (series) {
    wrap.appendChild(
      contextRow(
        el("div", "muted", `${series}${seriesIndex ? ` #${seriesIndex}` : ""}`),
        canOpen && seriesId
          ? contextAction(`/library/?view=series&series=${encodeURIComponent(seriesId)}`, "View series in Library", `View ${series} in Library`)
          : null,
      )
    );
  }

  container.appendChild(wrap);
}

function contextRow(labelNode, actionNode) {
  const row = el("div", "library-context-row");
  row.appendChild(labelNode);
  if (actionNode) row.appendChild(actionNode);
  return row;
}

function contextAction(href, label, accessibleLabel) {
  const link = el("a", "library-context-action", label);
  link.href = href;
  link.setAttribute("aria-label", accessibleLabel);
  link.setAttribute("title", accessibleLabel);
  return link;
}

function sortAnnotations(rows, sortKey) {
  const arr = Array.isArray(rows) ? rows.slice() : [];
  arr.sort((a, b) => {
    const au = a && a.updated_at ? new Date(String(a.updated_at)).getTime() : 0;
    const bu = b && b.updated_at ? new Date(String(b.updated_at)).getTime() : 0;
    return sortKey === "oldest" ? au - bu : bu - au;
  });
  return arr;
}

function renderAnnotationRow(a) {
  const wrap = document.createElement("article");
  wrap.className = "card annotation-card";

  const updatedAt = a && a.updated_at ? String(a.updated_at) : "";
  const createdAt = a && a.created_at ? String(a.created_at) : "";

  const bodies = Array.isArray(a && a.body) ? a.body : [];
  const quoteBody = bodies.find((b) => b && b.type === "TextualBody" && b.purpose === "describing");
  const noteBody = bodies.find((b) => b && b.type === "TextualBody" && b.purpose === "commenting");

  const quoteText = quoteBody && typeof quoteBody.value === "string" ? quoteBody.value : "";
  const noteText = noteBody && typeof noteBody.value === "string" ? noteBody.value : "";
  const hasQuote = !!quoteText;
  const hasNote = !!noteText;
  const motivation = a && a.motivation ? String(a.motivation) : "";
  const selectorValue =
    a && a.target && a.target.selector && typeof a.target.selector.value === "string"
      ? a.target.selector.value
      : "";
  const isBookmarkOnly = motivation === "bookmarking" && !hasQuote && !hasNote;

  let kindLabel = "Annotation";
  let kindIcon = "edit_note";
  if (isBookmarkOnly) {
    kindLabel = "Bookmark";
    kindIcon = "bookmark";
  } else if (hasQuote && hasNote) {
    kindLabel = "Highlight with note";
    kindIcon = "chat_bubble";
  } else if (hasNote && !hasQuote) {
    kindLabel = "Annotation";
    kindIcon = "edit_note";
  } else if (hasQuote && !hasNote) {
    kindLabel = "Highlight";
    kindIcon = "border_color";
  }

  const bodyWrap = document.createElement("div");
  bodyWrap.className = "annotation-card__body";

  const iconWrap = document.createElement("div");
  iconWrap.className = "annotation-card__icon";
  const icon = el("span", "material-symbols-outlined", kindIcon);
  icon.setAttribute("title", kindLabel);
  icon.setAttribute("aria-hidden", "true");
  iconWrap.appendChild(icon);
  iconWrap.appendChild(el("span", "sr-only", kindLabel));

  const contentWrap = document.createElement("div");
  contentWrap.className = "annotation-card__content";

  if (quoteText) {
    let token = quoteBody && typeof quoteBody.color === "string" ? quoteBody.color : "";
    token = (token || "").trim().toLowerCase();
    const allowed = new Set(["yellow", "green", "blue", "pink", "purple", "orange"]);
    if (!token || !allowed.has(token)) token = "yellow";

    const quoteEl = el("div", `annotation-quote annotation-quote--${token}`, quoteText);
    contentWrap.appendChild(quoteEl);
  }

  if (noteText) {
    const noteEl = el("div", "annotation-note", noteText);
    contentWrap.appendChild(noteEl);
  }

  if (isBookmarkOnly) {
    const titleEl = el("div", "", "Bookmark");
    const locationEl = el("div", "muted", "Saved location");
    if (selectorValue) {
      titleEl.setAttribute("title", selectorValue);
      locationEl.setAttribute("title", selectorValue);
    }
    contentWrap.appendChild(titleEl);
    contentWrap.appendChild(locationEl);
  } else if (!quoteText && !noteText) {
    const fallback = selectorValue ? selectorValue : "Bookmark";
    contentWrap.appendChild(el("div", "muted", fallback));
  }

  const whenText = updatedAt ? formatWhen(updatedAt) : createdAt ? formatWhen(createdAt) : "";
  contentWrap.appendChild(el("div", "muted annotation-meta", whenText));

  bodyWrap.appendChild(iconWrap);
  bodyWrap.appendChild(contentWrap);
  wrap.appendChild(bodyWrap);

  return wrap;
}

export function renderAnnotations(container, rows, sortKey) {
  clear(container);
  const sorted = sortAnnotations(rows, sortKey);
  if (!sorted.length) {
    container.appendChild(el("div", "muted", "No annotations yet."));
    return;
  }
  for (const a of sorted) {
    container.appendChild(renderAnnotationRow(a));
  }
}

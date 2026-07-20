function clear(node) {
  if (!node) return;
  while (node.firstChild) node.removeChild(node.firstChild);
}

function placeholder(titleText) {
  const ph = document.createElement("div");
  ph.className = "book__cover-ph";
  ph.textContent = "Cover";
  ph.setAttribute("aria-hidden", "true");
  if (titleText) ph.setAttribute("title", titleText);
  return ph;
}

export function mountCovers(root) {
  if (!root) return;
  const nodes = Array.from(root.querySelectorAll("[data-cover-url]"));
  for (const el of nodes) {
    if (!el || el.nodeType !== 1) continue;
    if (el.dataset && el.dataset.coverMounted === "1") continue;
    if (el.dataset) el.dataset.coverMounted = "1";

    const coverUrl = el.dataset ? String(el.dataset.coverUrl || "") : "";
    const titleText = el.dataset ? String(el.dataset.coverTitle || "") : "";
    clear(el);

    if (!coverUrl) {
      el.appendChild(placeholder(titleText));
      continue;
    }

    const img = document.createElement("img");
    img.className = "book__cover-img";
    img.alt = titleText || "Cover";
    img.loading = "lazy";
    img.src = coverUrl;
    img.addEventListener("error", () => {
      clear(el);
      el.appendChild(placeholder(titleText));
    });

    el.appendChild(img);
  }
}

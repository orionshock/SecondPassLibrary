import { fetchAllPaginatedResults } from "../api.js";

export function catalogTagOptions(tags, activeSlug) {
  const active = String(activeSlug || "");
  const options = [{ slug: "", name: "All tags", bookCount: null, active: !active }];
  for (const tag of Array.isArray(tags) ? tags : []) {
    const slug = tag && tag.slug ? String(tag.slug) : "";
    const name = tag && tag.name ? String(tag.name) : "";
    if (!slug || !name) continue;
    const count = Number(tag.book_count);
    options.push({
      slug,
      name,
      bookCount: Number.isFinite(count) ? count : 0,
      active: slug === active,
    });
  }
  return options;
}

function tagButton(option) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "library-tag-filter__option";
  button.dataset.tagSlug = option.slug;
  button.setAttribute("aria-pressed", option.active ? "true" : "false");
  if (option.active) button.classList.add("is-active");

  const name = document.createElement("span");
  name.textContent = option.name;
  button.appendChild(name);
  if (option.bookCount !== null) {
    const count = document.createElement("span");
    count.className = "library-tag-filter__count";
    count.textContent = String(option.bookCount);
    button.appendChild(count);
  }
  return button;
}

export async function initCatalogTagFilter({ container, getActiveSlug, onSelect }) {
  let tags = [];
  let error = "";
  const disclosure = container.closest("details");
  const narrowScreen = window.matchMedia("(max-width: 720px)");

  function syncDisclosure(event) {
    if (disclosure) disclosure.open = !event.matches;
  }
  syncDisclosure(narrowScreen);
  narrowScreen.addEventListener("change", syncDisclosure);

  function render() {
    container.replaceChildren();
    for (const option of catalogTagOptions(error ? [] : tags, getActiveSlug())) {
      container.appendChild(tagButton(option));
    }
    if (error) {
      const message = document.createElement("span");
      message.className = "error";
      message.textContent = error;
      container.appendChild(message);
    }
  }

  container.textContent = "Loading tags...";
  container.addEventListener("click", async (event) => {
    const source = event.target instanceof Element ? event.target : null;
    const button = source ? source.closest("button[data-tag-slug]") : null;
    if (!button || !container.contains(button)) return;
    const slug = button.dataset.tagSlug || "";
    await onSelect(slug && slug === getActiveSlug() ? "" : slug);
  });

  try {
    tags = await fetchAllPaginatedResults("/api/v1/library/tags/");
  } catch (cause) {
    console.error("Failed to load Library Catalog Tags", cause);
    error = "Unable to load Catalog Tags.";
  }
  render();
  return { sync: render };
}

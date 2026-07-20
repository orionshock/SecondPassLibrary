import { clear, el } from "./shared.js";

function normalizedName(value) {
  return String(value || "").normalize("NFKC").trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

export function renderCatalogTags({ state, selectedEl, optionsEl }) {
  clear(selectedEl);
  if (!state.catalogTags.length) selectedEl.appendChild(el("span", "muted", "No Catalog Tags."));
  for (const tag of state.catalogTags) {
    const pill = el("span", "pill catalog-tag-pill");
    pill.appendChild(el("span", "catalog-tag-pill__name", tag.name));
    const remove = el("button", "catalog-tag-pill__remove", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${tag.name}`);
    remove.setAttribute("data-remove-catalog-tag", tag.name);
    pill.appendChild(document.createTextNode(" "));
    pill.appendChild(remove);
    selectedEl.appendChild(pill);
    selectedEl.appendChild(document.createTextNode(" "));
  }

  clear(optionsEl);
  for (const tag of state.allCatalogTags) {
    const option = document.createElement("option");
    option.value = tag.name;
    optionsEl.appendChild(option);
  }
}

export function bindCatalogTagActions({ state, selectedEl, inputEl, addBtnEl, rerender, markDirty }) {
  addBtnEl.addEventListener("click", () => {
    const name = String(inputEl.value || "").normalize("NFKC").trim().replace(/\s+/g, " ");
    if (!name) return;
    const normalized = normalizedName(name);
    if (!state.catalogTags.some((tag) => normalizedName(tag.name) === normalized)) {
      const existing = state.allCatalogTags.find((tag) => normalizedName(tag.name) === normalized);
      state.catalogTags.push(existing || { name });
      markDirty();
    }
    inputEl.value = "";
    rerender();
  });

  selectedEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!target || !target.getAttribute) return;
    const name = target.getAttribute("data-remove-catalog-tag");
    if (!name) return;
    const normalized = normalizedName(name);
    state.catalogTags = state.catalogTags.filter((tag) => normalizedName(tag.name) !== normalized);
    markDirty();
    rerender();
  });
}

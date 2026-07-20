import { clear, el, fillSchemeOptions } from "./shared.js";

export function renderHeader({ book, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerDownloadEl }) {
  const title = book && book.title ? String(book.title) : "Book";
  headerTitleEl.textContent = title;

  const authorNames = Array.isArray(book && book.authors) ? book.authors.map((a) => a && a.name).filter(Boolean) : [];
  headerAuthorsEl.textContent = authorNames.length ? `Authors: ${authorNames.join(", ")}` : "Authors: (none)";

  const seriesName = book && book.series && book.series.name ? String(book.series.name) : "";
  const seriesIdx = book && book.series && book.series.series_index != null ? String(book.series.series_index) : "";
  headerSeriesEl.textContent = seriesName ? `Series: ${seriesName}${seriesIdx ? ` ${seriesIdx}` : ""}` : "Series: (none)";

  const file = book && book.file ? book.file : null;
  const downloadUrl = file && file.download_url ? String(file.download_url) : "";
  if (downloadUrl) headerDownloadEl.setAttribute("href", downloadUrl);
  else headerDownloadEl.removeAttribute("href");
  headerDownloadEl.classList.toggle("is-hidden", !downloadUrl);
}

export function renderFileInfo({ book, fileInfoEl }) {
  clear(fileInfoEl);
  fileInfoEl.appendChild(el("h3", "card__title", "File info"));
  const file = book && book.file ? book.file : null;
  if (!file) {
    fileInfoEl.appendChild(el("div", "muted", "No stored file."));
    return;
  }
  const kv = el("div", "kv");
  function addRow(k, vNodeOrText) {
    kv.appendChild(el("div", "kv__k", k));
    const v = el("div", "kv__v");
    if (vNodeOrText && vNodeOrText.nodeType) v.appendChild(vNodeOrText);
    else v.textContent = vNodeOrText != null ? String(vNodeOrText) : "";
    kv.appendChild(v);
  }
  addRow("Format", file.format ? String(file.format).toUpperCase() : "EPUB");
  addRow("Size", file.file_size != null && file.file_size !== "" ? `${String(file.file_size)} bytes` : "");
  addRow("Checksum", file.checksum ? String(file.checksum) : "");
  fileInfoEl.appendChild(kv);
}

export function renderIdentifiersTable({ identifiers, identifiersEl }) {
  clear(identifiersEl);
  const wrap = el("div", "ident-tablewrap");
  const table = el("table", "ident-table");
  const thead = document.createElement("thead");
  const trh = document.createElement("tr");
  for (const h of ["Scheme", "Value", "Actions"]) trh.appendChild(el("th", "", h));
  thead.appendChild(trh);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  const items = identifiers
    .slice()
    .sort((a, b) => `${a.scheme || ""}:${a.value || ""}`.localeCompare(`${b.scheme || ""}:${b.value || ""}`));

  for (const it of items) {
    const tr = document.createElement("tr");
    const identId = it && it.id != null ? String(it.id) : "";
    tr.setAttribute("data-ident-id", identId);

    const tdScheme = document.createElement("td");
    const schemeSel = document.createElement("select");
    schemeSel.setAttribute("data-ident-field", "scheme");
    fillSchemeOptions(schemeSel, it && it.scheme ? it.scheme : "other");
    tdScheme.appendChild(schemeSel);
    tr.appendChild(tdScheme);

    const tdValue = document.createElement("td");
    const valueInput = document.createElement("input");
    valueInput.type = "text";
    valueInput.style.width = "100%";
    valueInput.setAttribute("data-ident-field", "value");
    valueInput.value = it && it.value != null ? String(it.value) : "";
    tdValue.appendChild(valueInput);
    tr.appendChild(tdValue);

    const tdActions = document.createElement("td");
    const saveBtn = el("button", "button", "Save");
    saveBtn.type = "button";
    saveBtn.setAttribute("data-ident-action", "save");
    const delBtn = el("button", "button", "Delete");
    delBtn.type = "button";
    delBtn.style.marginLeft = "6px";
    delBtn.setAttribute("data-ident-action", "delete");
    const status = el("span", "muted");
    status.style.marginLeft = "10px";
    status.setAttribute("data-ident-status", "");
    tdActions.appendChild(saveBtn);
    tdActions.appendChild(delBtn);
    tdActions.appendChild(status);
    tr.appendChild(tdActions);

    tbody.appendChild(tr);
  }

  // Add row
  const trAdd = document.createElement("tr");
  trAdd.setAttribute("data-ident-id", "");
  const tdAScheme = document.createElement("td");
  const schemeSel = document.createElement("select");
  schemeSel.setAttribute("data-ident-field", "scheme");
  fillSchemeOptions(schemeSel, "isbn_13");
  tdAScheme.appendChild(schemeSel);
  trAdd.appendChild(tdAScheme);

  const tdAValue = document.createElement("td");
  const valueInput = document.createElement("input");
  valueInput.type = "text";
  valueInput.style.width = "100%";
  valueInput.setAttribute("data-ident-field", "value");
  tdAValue.appendChild(valueInput);
  trAdd.appendChild(tdAValue);

  const tdAActions = document.createElement("td");
  const addBtn = el("button", "button", "Add");
  addBtn.type = "button";
  addBtn.setAttribute("data-ident-action", "add");
  const addStatus = el("span", "muted");
  addStatus.setAttribute("data-ident-status", "");
  tdAActions.appendChild(addBtn);
  tdAActions.appendChild(addStatus);
  trAdd.appendChild(tdAActions);

  tbody.appendChild(trAdd);
  table.appendChild(tbody);
  wrap.appendChild(table);
  identifiersEl.appendChild(wrap);
}

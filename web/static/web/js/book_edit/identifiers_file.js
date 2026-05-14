import { clear, el, fillSchemeOptions } from "./shared.js";

export function renderHeader({ book, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl }) {
  const title = book && book.title ? String(book.title) : "Book";
  headerTitleEl.textContent = title;

  const authorNames = Array.isArray(book && book.authors) ? book.authors.map((a) => a && a.name).filter(Boolean) : [];
  headerAuthorsEl.textContent = authorNames.length ? `Authors: ${authorNames.join(", ")}` : "Authors: (none)";

  const seriesName = book && book.series && book.series.name ? String(book.series.name) : "";
  const seriesIdx = book && book.series_index != null && book.series_index !== "" ? String(book.series_index) : "";
  headerSeriesEl.textContent = seriesName ? `Series: ${seriesName}${seriesIdx ? " · " + seriesIdx : ""}` : "Series: (none)";

  clear(headerFileEl);
  const file = book && book.file ? book.file : null;
  if (!file) {
    headerFileEl.appendChild(el("span", "pill", "No file"));
    return;
  }
  const fmt = file.format ? String(file.format).toUpperCase() : "EPUB";
  const downloadUrl = file.download_url ? String(file.download_url) : "";
  if (downloadUrl) {
    const a = el("a", "pill", `Download ${fmt}`);
    a.setAttribute("href", downloadUrl);
    headerFileEl.appendChild(a);
  } else {
    headerFileEl.appendChild(el("span", "pill", fmt));
  }
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
  addRow("Checksum", file.checksum_short ? String(file.checksum_short) : "");
  if (file.download_url) {
    const a = el("a", "pill", "Download");
    a.setAttribute("href", String(file.download_url));
    addRow("Download", a);
  } else {
    addRow("Download", "");
  }
  fileInfoEl.appendChild(kv);
}

export function renderIdentifiersTable({ identifiers, identifiersEl }) {
  clear(identifiersEl);
  const wrap = el("div", "ident-tablewrap");
  const table = el("table", "ident-table");
  const thead = document.createElement("thead");
  const trh = document.createElement("tr");
  for (const h of ["Scheme", "Value", "Source", "Primary", "Actions"]) trh.appendChild(el("th", "", h));
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

    const tdSource = document.createElement("td");
    const sourceInput = document.createElement("input");
    sourceInput.type = "text";
    sourceInput.style.width = "100%";
    sourceInput.setAttribute("data-ident-field", "source");
    sourceInput.value = it && it.source != null ? String(it.source) : "";
    tdSource.appendChild(sourceInput);
    tr.appendChild(tdSource);

    const tdPrimary = document.createElement("td");
    tdPrimary.style.textAlign = "center";
    const primaryInput = document.createElement("input");
    primaryInput.type = "checkbox";
    primaryInput.setAttribute("data-ident-field", "is_primary");
    primaryInput.checked = !!(it && it.is_primary);
    tdPrimary.appendChild(primaryInput);
    tr.appendChild(tdPrimary);

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

  const tdASource = document.createElement("td");
  const sourceInput = document.createElement("input");
  sourceInput.type = "text";
  sourceInput.style.width = "100%";
  sourceInput.setAttribute("data-ident-field", "source");
  tdASource.appendChild(sourceInput);
  trAdd.appendChild(tdASource);

  const tdAPrimary = document.createElement("td");
  tdAPrimary.style.textAlign = "center";
  const primaryInput = document.createElement("input");
  primaryInput.type = "checkbox";
  primaryInput.setAttribute("data-ident-field", "is_primary");
  primaryInput.checked = false;
  tdAPrimary.appendChild(primaryInput);
  trAdd.appendChild(tdAPrimary);

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


import { renderIdentifiersTable } from "./identifiers_file.js";
import { setStatus } from "../ui/status.js";

let nextTemporaryIdentifierId = 1;

export function refreshIdentifiersContext({ identifiersStatusEl, identifiersEl, state }) {
  setStatus(identifiersStatusEl, "", false);
  renderIdentifiersTable({ identifiers: state.identifiers, identifiersEl });
}

function identifierPayload(row, selectorPrefix) {
  const schemeEl = row.querySelector(`[${selectorPrefix}="scheme"]`);
  const valueEl = row.querySelector(`[${selectorPrefix}="value"]`);
  return {
    scheme: schemeEl && schemeEl.value != null ? String(schemeEl.value).trim() : "",
    value: valueEl && valueEl.value != null ? String(valueEl.value).trim() : "",
  };
}

export function bindIdentifierActions({ identifiersEl, refreshIdentifiers, state, setError, markDirty }) {
  identifiersEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!target || !target.getAttribute) return;
    const action = target.getAttribute("data-ident-action");
    if (!action) return;

    const row = target.closest ? target.closest("tr") : null;
    if (!row) return;

    if (action === "add") {
      const payload = identifierPayload(row, "data-ident-field");
      if (!payload.value) {
        setError("Identifier value is required.");
        return;
      }
      state.identifiers.push({ id: `new-${nextTemporaryIdentifierId}`, ...payload });
      nextTemporaryIdentifierId += 1;
    } else {
      const identifierId = row.getAttribute("data-ident-id") || "";
      const index = state.identifiers.findIndex(
        (identifier) => String(identifier.id) === String(identifierId)
      );
      if (index < 0) return;

      if (action === "delete") {
        state.identifiers.splice(index, 1);
      } else if (action === "save") {
        const payload = identifierPayload(row, "data-ident-field");
        if (!payload.value) {
          setError("Identifier value is required.");
          return;
        }
        state.identifiers[index] = { ...state.identifiers[index], ...payload };
      } else {
        return;
      }
    }

    setError("");
    markDirty();
    refreshIdentifiers();
  });
}

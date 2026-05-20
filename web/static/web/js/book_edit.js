// Compatibility re-export.
// The product UI bootstrap (`main.js`) dynamically imports page modules directly.
// Keep this module to avoid breaking any older imports or external references.
export { initBookEdit } from "./book_edit/main.js";

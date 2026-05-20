// Compatibility re-exports.
// The product UI bootstrap (`main.js`) dynamically imports page modules directly.
// Keep this module to avoid breaking any older imports or external references.
export {
  initGroupsList,
  initGroupView,
  initGroupEdit,
  initGroupDetail,
  initGroupNew,
} from "./groups/main.js";

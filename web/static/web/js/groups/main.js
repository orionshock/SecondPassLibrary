import { initGroupView } from "./view.js";

export { initGroupsList } from "./list.js";
export { initGroupEdit } from "./edit.js";
export { initGroupView } from "./view.js";

// Backwards-compatible export name (used by older page ids / imports).
export async function initGroupDetail() {
  return initGroupView();
}

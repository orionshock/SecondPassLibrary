import {
  initAppHeaderLayout,
  loadMeAndInitShell,
  setGlobalErrorFromError,
} from "./layout.js";

async function runPageInit({ importer, initExportName, label }) {
  try {
    const mod = await importer();
    const initFn = mod && mod[initExportName];
    if (typeof initFn !== "function") {
      throw new Error(`Module did not export ${initExportName}`);
    }
    await initFn();
  } catch (e) {
    console.error(`${initExportName} failed`, e);
    setGlobalErrorFromError(e, `${label} error:`);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initAppHeaderLayout();
  const page = document.body && document.body.dataset ? document.body.dataset.page : "";

  const registry = {
    app: { importer: () => import("./dashboard/main.js"), initExportName: "initDashboard", label: "App" },
    library: { importer: () => import("./library/list.js"), initExportName: "initLibraryBrowse", label: "Library" },
    "book-detail": { importer: () => import("./library/detail.js"), initExportName: "initBookDetail", label: "Book" },
    "reading-book-activity": {
      importer: () => import("./reading/activity.js"),
      initExportName: "initReadingBookActivity",
      label: "Reading activity",
    },
    "reading-sessions": {
      importer: () => import("./reading/sessions.js"),
      initExportName: "initReadingSessions",
      label: "Reading sessions",
    },
    "reading-import": {
      importer: () => import("./reading/import_preview.js"),
      initExportName: "initReadingImportPreview",
      label: "Import marginalia",
    },
    "book-edit": { importer: () => import("./book_edit/main.js"), initExportName: "initBookEdit", label: "Book edit" },
    imports: { importer: () => import("./imports/main.js"), initExportName: "initImports", label: "Imports" },

    shelves: { importer: () => import("./shelves/main.js"), initExportName: "initShelvesList", label: "Shelves" },
    "shelf-new": { importer: () => import("./shelves/main.js"), initExportName: "initShelfNew", label: "New shelf" },
    "shelf-view": { importer: () => import("./shelves/main.js"), initExportName: "initShelfView", label: "Shelf" },
    "shelf-edit": { importer: () => import("./shelves/main.js"), initExportName: "initShelfEdit", label: "Shelf edit" },

    groups: { importer: () => import("./groups/main.js"), initExportName: "initGroupsList", label: "Groups" },
    "group-new": { importer: () => import("./groups/main.js"), initExportName: "initGroupNew", label: "New group" },
    "group-view": { importer: () => import("./groups/main.js"), initExportName: "initGroupView", label: "Group" },
    "group-edit": { importer: () => import("./groups/main.js"), initExportName: "initGroupEdit", label: "Group edit" },

    users: { importer: () => import("./users/main.js"), initExportName: "initUsersList", label: "Users" },
    "user-new": { importer: () => import("./users/main.js"), initExportName: "initUserNew", label: "Create user" },
    "user-edit": { importer: () => import("./users/main.js"), initExportName: "initUserEdit", label: "Edit user" },

    profile: { importer: () => import("./profile/main.js"), initExportName: "initProfile", label: "Profile" },
    "profile-password": {
      importer: () => import("./profile/password.js"),
      initExportName: "initProfilePassword",
      label: "Password",
    },
    "server-settings": {
      importer: () => import("./server/settings.js"),
      initExportName: "initServerSettings",
      label: "Server settings",
    },
  };

  const entry = registry[page];
  if (entry) {
    runPageInit(entry);
    return;
  }

  loadMeAndInitShell().catch((e) => {
    console.error("Shell init failed", e);
    setGlobalErrorFromError(e, "UI error:");
  });
});

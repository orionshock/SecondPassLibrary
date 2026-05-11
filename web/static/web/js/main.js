import { loadMeAndInitShell, setGlobalErrorFromError } from "./layout.js";
import { initDashboard } from "./app_page.js";
import { initLibraryBrowse } from "./library.js";
import { initBookDetail } from "./book_detail.js";
import { initBookEdit } from "./book_edit.js";
import { initImports } from "./imports.js";
import { initGroupsList, initGroupView, initGroupEdit } from "./groups.js";
import { initProfile } from "./profile.js";
import { initProfilePassword } from "./profile_password.js";
import { initUsersList, initUserNew, initUserEdit } from "./users.js";

document.addEventListener("DOMContentLoaded", () => {
  const page = document.body && document.body.dataset ? document.body.dataset.page : "";
  if (page === "app") {
    initDashboard().catch((e) => {
      console.error("initDashboard failed", e);
      setGlobalErrorFromError(e, "App error:");
    });
  } else if (page === "library") {
    initLibraryBrowse().catch((e) => {
      console.error("initLibraryBrowse failed", e);
      setGlobalErrorFromError(e, "Library error:");
    });
  } else if (page === "book-detail") {
    initBookDetail().catch((e) => {
      console.error("initBookDetail failed", e);
      setGlobalErrorFromError(e, "Book error:");
    });
  } else if (page === "book-edit") {
    initBookEdit().catch((e) => {
      console.error("initBookEdit failed", e);
      setGlobalErrorFromError(e, "Book edit error:");
    });
  } else if (page === "imports") {
    initImports().catch((e) => {
      console.error("initImports failed", e);
      setGlobalErrorFromError(e, "Imports error:");
    });
  } else if (page === "groups") {
    initGroupsList().catch((e) => {
      console.error("initGroupsList failed", e);
      setGlobalErrorFromError(e, "Groups error:");
    });
  } else if (page === "group-view") {
    initGroupView().catch((e) => {
      console.error("initGroupView failed", e);
      setGlobalErrorFromError(e, "Group error:");
    });
  } else if (page === "group-edit") {
    initGroupEdit().catch((e) => {
      console.error("initGroupEdit failed", e);
      setGlobalErrorFromError(e, "Group edit error:");
    });
  } else if (page === "users") {
    initUsersList().catch((e) => {
      console.error("initUsersList failed", e);
      setGlobalErrorFromError(e, "Users error:");
    });
  } else if (page === "user-new") {
    initUserNew().catch((e) => {
      console.error("initUserNew failed", e);
      setGlobalErrorFromError(e, "Create user error:");
    });
  } else if (page === "user-edit") {
    initUserEdit().catch((e) => {
      console.error("initUserEdit failed", e);
      setGlobalErrorFromError(e, "Edit user error:");
    });
  } else if (page === "profile") {
    initProfile().catch((e) => {
      console.error("initProfile failed", e);
      setGlobalErrorFromError(e, "Profile error:");
    });
  } else if (page === "profile-password") {
    initProfilePassword().catch((e) => {
      console.error("initProfilePassword failed", e);
      setGlobalErrorFromError(e, "Password error:");
    });
  } else {
    loadMeAndInitShell().catch((e) => {
      console.error("Shell init failed", e);
      setGlobalErrorFromError(e, "UI error:");
    });
  }
});

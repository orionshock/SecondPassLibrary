import { extractApiErrorMessage, fetchJSONWithOptions, getCsrfToken } from "../api.js";
import { setGlobalError, visible } from "../layout.js";
import { setElStatus } from "./shared.js";

export function initManagedPasswordReset({
  userId,
  canResetPassword,
  resetBtn,
  resetStatus,
  resetResult,
  resetCopy,
  refreshUserAndMemberships,
}) {
  function setResetStatus(text, isError) {
    setElStatus(resetStatus, text, isError);
  }

  resetBtn.addEventListener("click", async () => {
    setGlobalError("");
    setResetStatus("Resettingâ€¦", false);
    visible(resetResult, false);
    resetCopy.value = "";

    if (!canResetPassword) {
      setResetStatus("Not allowed.", true);
      return;
    }

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const payload = await fetchJSONWithOptions(`/api/v1/accounts/users/${encodeURIComponent(String(userId))}/reset-password/`, {
        method: "POST",
        headers,
      });

      const copyBlock = payload && payload.copy_block ? String(payload.copy_block) : "";
      if (!copyBlock) throw new Error("Unexpected response from server.");

      resetCopy.value = copyBlock;
      visible(resetResult, true);
      setResetStatus("Reset.", false);

      // Refresh user to show must_change_password=true.
      await refreshUserAndMemberships();
    } catch (e2) {
      console.error("Failed to reset password", { userId, e2 });
      const msg = extractApiErrorMessage(e2);
      setResetStatus(msg, true);
      setGlobalError(msg);
    }
  });
}


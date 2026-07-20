import { extractApiErrorMessage, fetchJSONWithOptions, getCsrfToken } from "../api.js";
import { setGlobalError, visible } from "../layout.js";
import { setStatus } from "../ui/status.js";

export function initManagedPasswordReset({
  profileId,
  canResetPassword,
  resetBtn,
  resetStatus,
  resetResult,
  resetCopy,
  refreshUserAndMemberships,
}) {
  resetBtn.addEventListener("click", async () => {
    setGlobalError("");
    setStatus(resetStatus, "Resetting...", false);
    visible(resetResult, false);
    resetCopy.value = "";

    if (!canResetPassword) {
      setStatus(resetStatus, "Not allowed.", true);
      return;
    }

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const payload = await fetchJSONWithOptions(`/api/v1/accounts/users/${encodeURIComponent(String(profileId))}/reset-password/`, {
        method: "POST",
        headers,
      });

      const copyBlock = payload && payload.copy_block ? String(payload.copy_block) : "";
      if (!copyBlock) throw new Error("Unexpected response from server.");

      resetCopy.value = copyBlock;
      visible(resetResult, true);
      setStatus(resetStatus, "Reset.", false);

      // Refresh user to show must_change_password=true.
      await refreshUserAndMemberships();
    } catch (e2) {
      console.error("Failed to reset password", { profileId, e2 });
      const msg = extractApiErrorMessage(e2);
      setStatus(resetStatus, msg, true);
      setGlobalError(msg);
    }
  });
}

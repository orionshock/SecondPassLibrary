/** @vitest-environment happy-dom */

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";

const projectRoot = existsSync(resolve(process.cwd(), "backend"))
  ? process.cwd()
  : resolve(process.cwd(), "..");
const templatePath = resolve(projectRoot, "backend/web/templates/web/setup.html");

function setupScript() {
  const template = readFileSync(templatePath, "utf8");
  const scripts = [...template.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  const script = scripts.at(-1)?.[1];
  if (!script) throw new Error("Setup page script not found.");
  return script;
}

function installSetupDom({ invalid = false, supportsDialog = true } = {}) {
  document.body.innerHTML = `
    <form data-advanced-groups-confirm="Enable Advanced Library Groups?">
      <input name="username" autofocus>
      <input name="password2" ${invalid ? 'aria-invalid="true"' : ""}>
      <input name="advanced_library_groups_enabled" type="checkbox">
      <button id="setup-advanced-groups-open" type="button">Enable</button>
      <div id="setup-advanced-groups-enabled-status" class="is-hidden">
        <button id="setup-advanced-groups-disable" type="button">Keep disabled</button>
      </div>
      <button type="submit" data-setup-submit data-pending-label="Completing setup...">Complete setup</button>
    </form>
    <dialog id="setup-advanced-groups-dialog">
      <button id="setup-advanced-groups-cancel" value="cancel">Keep disabled</button>
    </dialog>`;

  const dialog = document.querySelector("dialog");
  Object.defineProperty(dialog, "showModal", {
    configurable: true,
    value: supportsDialog ? vi.fn() : undefined,
  });
  window.eval(setupScript());
  return {
    form: document.querySelector("form"),
    checkbox: document.querySelector("[name='advanced_library_groups_enabled']"),
    dialog,
    openButton: document.querySelector("#setup-advanced-groups-open"),
    disableButton: document.querySelector("#setup-advanced-groups-disable"),
    enabledStatus: document.querySelector("#setup-advanced-groups-enabled-status"),
    submitButton: document.querySelector("[data-setup-submit]"),
  };
}

beforeEach(() => {
  document.body.replaceChildren();
  vi.restoreAllMocks();
});

describe("Django Setup page script", () => {
  it("confirms Advanced Groups through the dialog and can reset to disabled", () => {
    const controls = installSetupDom();
    const cancel = document.querySelector("#setup-advanced-groups-cancel");

    controls.dialog.returnValue = "stale";
    controls.openButton.click();
    expect(controls.dialog.returnValue).toBe("");
    expect(controls.dialog.showModal).toHaveBeenCalledOnce();
    expect(document.activeElement).toBe(cancel);

    controls.dialog.returnValue = "cancel";
    controls.dialog.dispatchEvent(new Event("close"));
    expect(controls.checkbox.checked).toBe(false);

    controls.dialog.returnValue = "enable";
    controls.dialog.dispatchEvent(new Event("close"));
    expect(controls.checkbox.checked).toBe(true);
    expect(controls.openButton.classList.contains("is-hidden")).toBe(true);
    expect(controls.enabledStatus.classList.contains("is-hidden")).toBe(false);

    controls.disableButton.click();
    expect(controls.checkbox.checked).toBe(false);
    expect(controls.openButton.classList.contains("is-hidden")).toBe(false);
    expect(controls.enabledStatus.classList.contains("is-hidden")).toBe(true);
  });

  it("falls back to confirmation when the dialog API is unavailable", () => {
    const confirm = vi.fn().mockReturnValueOnce(false).mockReturnValueOnce(true);
    window.confirm = confirm;
    const controls = installSetupDom({ supportsDialog: false });

    controls.openButton.click();
    expect(controls.checkbox.checked).toBe(false);
    expect(controls.openButton.classList.contains("is-hidden")).toBe(false);

    controls.openButton.click();
    expect(controls.checkbox.checked).toBe(true);
    expect(controls.openButton.classList.contains("is-hidden")).toBe(true);
    expect(controls.enabledStatus.classList.contains("is-hidden")).toBe(false);
    expect(confirm).toHaveBeenCalledTimes(2);
  });

  it("focuses the first invalid field and removes stale autofocus", () => {
    installSetupDom({ invalid: true });

    const username = document.querySelector("[name='username']");
    const password = document.querySelector("[name='password2']");
    expect(document.activeElement).toBe(password);
    expect(username.hasAttribute("autofocus")).toBe(false);
  });

  it("cancels rejected confirmation and locks an accepted submission", () => {
    const controls = installSetupDom();
    controls.checkbox.checked = true;
    const confirm = vi.fn().mockReturnValueOnce(false);
    window.confirm = confirm;

    const rejected = new Event("submit", { bubbles: true, cancelable: true });
    expect(controls.form.dispatchEvent(rejected)).toBe(false);
    expect(confirm).toHaveBeenCalledWith("Enable Advanced Library Groups?");
    expect(controls.form.hasAttribute("aria-busy")).toBe(false);
    expect(controls.submitButton.disabled).toBe(false);

    confirm.mockReturnValueOnce(true);
    const accepted = new Event("submit", { bubbles: true, cancelable: true });
    expect(controls.form.dispatchEvent(accepted)).toBe(true);
    expect(controls.form.getAttribute("aria-busy")).toBe("true");
    expect(controls.submitButton.disabled).toBe(true);
    expect(controls.submitButton.textContent).toBe("Completing setup...");
  });
});

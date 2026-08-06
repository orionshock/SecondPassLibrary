"use strict";

(function () {
    function setChecked(checkboxes, checked) {
        checkboxes.forEach(function (checkbox) {
            checkbox.checked = checked;
            checkbox.dispatchEvent(new Event("change", { bubbles: true }));
        });
    }

    function installBulkRemovalControls(group) {
        const checkboxes = Array.from(
            group.querySelectorAll('input[type="checkbox"][name$="-DELETE"]'),
        );
        const wrapper = group.querySelector(".wrapper");
        if (!wrapper || checkboxes.length === 0) {
            return;
        }

        const controls = document.createElement("div");
        controls.className = "catalog-tag-books-controls";

        const explanation = document.createElement("p");
        explanation.textContent =
            "Mark relationships for removal, then save the tag. Books and reading data are not deleted.";

        const markAll = document.createElement("button");
        markAll.type = "button";
        markAll.className = "button";
        markAll.textContent = "Mark all for removal";
        markAll.addEventListener("click", function () {
            setChecked(checkboxes, true);
        });

        const clearAll = document.createElement("button");
        clearAll.type = "button";
        clearAll.className = "button";
        clearAll.textContent = "Clear removal marks";
        clearAll.addEventListener("click", function () {
            setChecked(checkboxes, false);
        });

        controls.append(explanation, markAll, clearAll);
        wrapper.parentNode.insertBefore(controls, wrapper);
    }

    function install() {
        document
            .querySelectorAll(".catalog-tag-books-inline")
            .forEach(installBulkRemovalControls);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", install);
    } else {
        install();
    }
})();

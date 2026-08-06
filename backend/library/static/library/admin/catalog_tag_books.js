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

    function sortValue(row, field) {
        const cell = row.querySelector(".field-" + field);
        const value = cell ? cell.textContent.trim() : "";
        return value === "-" ? "" : value;
    }

    function compareValues(left, right, direction) {
        if (!left && right) {
            return 1;
        }
        if (left && !right) {
            return -1;
        }
        return (
            direction *
            left.localeCompare(right, undefined, {
                numeric: true,
                sensitivity: "base",
            })
        );
    }

    function installSortControls(group) {
        const tbody = group.querySelector("tbody");
        if (!tbody) {
            return;
        }
        const rows = Array.from(tbody.querySelectorAll("tr.form-row"));
        const fields = ["book_link", "primary_author_link", "series_link"];

        fields.forEach(function (field) {
            const header = group.querySelector("th.column-" + field);
            if (!header) {
                return;
            }
            const label = header.textContent.trim();
            const button = document.createElement("button");
            button.type = "button";
            button.className = "catalog-tag-sort";
            button.textContent = label;
            button.setAttribute("aria-label", "Sort by " + label);
            button.addEventListener("click", function () {
                const direction = header.getAttribute("aria-sort") === "ascending" ? -1 : 1;
                group.querySelectorAll("th[aria-sort]").forEach(function (item) {
                    item.removeAttribute("aria-sort");
                });
                header.setAttribute("aria-sort", direction === 1 ? "ascending" : "descending");
                rows
                    .map(function (row, index) {
                        return { row: row, index: index, value: sortValue(row, field) };
                    })
                    .sort(function (left, right) {
                        return (
                            compareValues(left.value, right.value, direction) ||
                            left.index - right.index
                        );
                    })
                    .forEach(function (item) {
                        tbody.appendChild(item.row);
                    });
            });
            header.textContent = "";
            header.appendChild(button);
        });
    }

    function install() {
        document
            .querySelectorAll(".catalog-tag-books-inline")
            .forEach(function (group) {
                installBulkRemovalControls(group);
                installSortControls(group);
            });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", install);
    } else {
        install();
    }
})();

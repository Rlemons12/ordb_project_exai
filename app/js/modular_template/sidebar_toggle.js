(() => {
    const STORAGE_KEY = "oracle_ai_sidebar_collapsed";
    const FLOATING_BUTTON_ID = "sidebar-floating-expand-button";

    function getBody() {
        return document.body;
    }

    function getCollapseButton() {
        return document.getElementById("sidebar-collapse-button");
    }

    function getSidebarContainer() {
        return document.getElementById("sidebar-container");
    }

    function getFloatingButton() {
        return document.getElementById(FLOATING_BUTTON_ID);
    }

    function isCollapsed() {
        return getBody().classList.contains("sidebar-collapsed");
    }

    function saveSidebarState(collapsed) {
        try {
            localStorage.setItem(STORAGE_KEY, collapsed ? "true" : "false");
        } catch (error) {
            // Local storage is optional.
        }
    }

    function loadSavedState() {
        try {
            return localStorage.getItem(STORAGE_KEY) === "true";
        } catch (error) {
            return false;
        }
    }

    function ensureFloatingButton() {
        let button = getFloatingButton();

        if (button) {
            return button;
        }

        button = document.createElement("button");
        button.id = FLOATING_BUTTON_ID;
        button.className = "sidebar-floating-expand-button";
        button.type = "button";
        button.title = "Show sidebar";
        button.setAttribute("aria-label", "Show sidebar");
        button.innerHTML = `
            <span aria-hidden="true">☰</span>
            <span class="sidebar-floating-expand-text">Menu</span>
        `;

        button.addEventListener("click", () => {
            applySidebarState(false);
        });

        document.body.appendChild(button);

        return button;
    }

    function applySidebarState(collapsed) {
        const body = getBody();
        const collapseButton = getCollapseButton();
        const sidebar = getSidebarContainer();
        const floatingButton = ensureFloatingButton();

        body.classList.toggle("sidebar-collapsed", collapsed);

        if (sidebar) {
            sidebar.classList.toggle("is-collapsed", collapsed);
            sidebar.setAttribute("aria-hidden", String(collapsed));
        }

        if (collapseButton) {
            collapseButton.setAttribute("aria-expanded", String(!collapsed));
            collapseButton.setAttribute(
                "title",
                collapsed ? "Expand sidebar" : "Collapse sidebar"
            );

            const label = collapseButton.querySelector(".sidebar-collapse-label");
            if (label) {
                label.textContent = collapsed ? "Expand" : "Collapse";
            }

            const icon = collapseButton.querySelector(".sidebar-collapse-icon");
            if (icon) {
                icon.textContent = collapsed ? "»" : "«";
            }
        }

        if (floatingButton) {
            floatingButton.hidden = !collapsed;
            floatingButton.setAttribute("aria-hidden", String(!collapsed));
        }

        saveSidebarState(collapsed);
    }

    function setupSidebarToggle() {
        const collapseButton = getCollapseButton();

        ensureFloatingButton();

        if (collapseButton) {
            collapseButton.addEventListener("click", () => {
                applySidebarState(!isCollapsed());
            });
        } else {
            console.warn("Sidebar collapse button not found.");
        }

        applySidebarState(loadSavedState());
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setupSidebarToggle);
    } else {
        setupSidebarToggle();
    }
})();
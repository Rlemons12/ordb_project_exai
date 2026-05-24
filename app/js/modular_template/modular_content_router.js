(() => {
    const contentContainer = document.getElementById("partial-container");

    if (!contentContainer) {
        return;
    }

    function setActiveSidebarLink(clickedLink) {
        document.querySelectorAll(".oracle-sidebar-link").forEach((link) => {
            link.removeAttribute("aria-current");
        });

        if (clickedLink) {
            clickedLink.setAttribute("aria-current", "page");
        }
    }

    async function loadPartial(url, browserUrl, pageTitle, clickedLink) {
        contentContainer.classList.add("is-loading");

        try {
            const response = await fetch(url, {
                method: "GET",
                headers: {
                    "X-Requested-With": "fetch",
                },
            });

            if (!response.ok) {
                throw new Error(`Failed to load content. Status: ${response.status}`);
            }

            const html = await response.text();

            contentContainer.innerHTML = html;

            if (browserUrl) {
                window.history.pushState(
                    {
                        contentUrl: url,
                        pageTitle: pageTitle || document.title,
                    },
                    "",
                    browserUrl
                );
            }

            if (pageTitle) {
                document.title = pageTitle;
            }

            setActiveSidebarLink(clickedLink);

            document.dispatchEvent(
                new CustomEvent("oracle-content-swapped", {
                    detail: {
                        contentUrl: url,
                        browserUrl,
                        pageTitle,
                    },
                })
            );
        } catch (error) {
            contentContainer.innerHTML = `
                <section class="oracle-content-card oracle-full-width">
                    <h2>Content Load Error</h2>
                    <p class="text-danger">${escapeHtml(error.message)}</p>
                </section>
            `;
        } finally {
            contentContainer.classList.remove("is-loading");
        }
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    document.addEventListener("click", (event) => {
        const link = event.target.closest(".oracle-sidebar-link[data-content-url]");

        if (!link) {
            return;
        }

        if (link.target === "_blank") {
            return;
        }

        event.preventDefault();

        const contentUrl = link.dataset.contentUrl;
        const browserUrl = link.getAttribute("href");
        const pageTitle = link.dataset.pageTitle;

        if (!contentUrl) {
            return;
        }

        loadPartial(contentUrl, browserUrl, pageTitle, link);
    });

    window.addEventListener("popstate", (event) => {
        const state = event.state;

        if (!state || !state.contentUrl) {
            window.location.reload();
            return;
        }

        loadPartial(
            state.contentUrl,
            null,
            state.pageTitle,
            document.querySelector(`.oracle-sidebar-link[data-content-url="${state.contentUrl}"]`)
        );
    });
})();
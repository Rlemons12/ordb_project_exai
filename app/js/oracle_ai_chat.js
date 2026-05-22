(() => {
    const form = document.getElementById("oracle-ai-form");
    const questionInput = document.getElementById("question");
    const includeSampleRowsInput = document.getElementById("include-sample-rows");
    const maxTablesInput = document.getElementById("max-tables");
    const maxResultRowsInput = document.getElementById("max-result-rows");
    const askButton = document.getElementById("ask-button");
    const clearButton = document.getElementById("clear-button");
    const schemaButton = document.getElementById("schema-button");
    const loadingBanner = document.getElementById("loading-banner");
    const answerOutput = document.getElementById("answer-output");
    const schemaOutput = document.getElementById("schema-output");
    const requestIdOutput = document.getElementById("request-id");
    const healthDot = document.getElementById("health-dot");
    const healthTitle = document.getElementById("health-title");
    const healthDetail = document.getElementById("health-detail");

    function setLoading(isLoading) {
        if (isLoading) {
            loadingBanner.classList.remove("is-hidden");
            askButton.disabled = true;
            schemaButton.disabled = true;
        } else {
            loadingBanner.classList.add("is-hidden");
            askButton.disabled = false;
            schemaButton.disabled = false;
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

    function formatJson(value) {
        return JSON.stringify(value, null, 2);
    }

    function renderRowsTable(rows) {
        if (!Array.isArray(rows) || rows.length === 0) {
            return "<p class=\"exai-muted\">No rows returned.</p>";
        }

        const columns = Object.keys(rows[0] || {});

        if (columns.length === 0) {
            return "<p class=\"exai-muted\">Rows were returned, but no columns were available.</p>";
        }

        const header = columns
            .map((column) => `<th>${escapeHtml(column)}</th>`)
            .join("");

        const body = rows
            .map((row) => {
                const cells = columns
                    .map((column) => `<td>${escapeHtml(row[column])}</td>`)
                    .join("");

                return `<tr>${cells}</tr>`;
            })
            .join("");

        return `
            <div class="exai-table-wrapper">
                <table class="exai-table">
                    <thead>
                        <tr>${header}</tr>
                    </thead>
                    <tbody>${body}</tbody>
                </table>
            </div>
        `;
    }

    function renderAnswer(result) {
        requestIdOutput.textContent = result.request_id
            ? `request_id=${result.request_id}`
            : "";

        const errorBlock = result.error
            ? `<div class="exai-alert"><strong>Error:</strong> ${escapeHtml(result.error)}</div>`
            : "";

        const sqlBlock = result.generated_sql
            ? `<pre class="exai-sql">${escapeHtml(result.generated_sql)}</pre>`
            : "<p class=\"exai-muted\">No SQL was generated.</p>";

        answerOutput.className = "exai-result-block";

        answerOutput.innerHTML = `
            ${errorBlock}

            <section>
                <h3>Explanation</h3>
                <div class="exai-explanation">${escapeHtml(result.explanation || "")}</div>
            </section>

            <section>
                <h3>Generated SQL</h3>
                ${sqlBlock}
            </section>

            <section>
                <h3>Result Rows (${escapeHtml(result.row_count ?? 0)})</h3>
                ${renderRowsTable(result.rows || [])}
            </section>

            <section>
                <h3>Raw Response</h3>
                <pre class="exai-pre">${escapeHtml(formatJson(result))}</pre>
            </section>
        `;
    }

    async function checkHealth() {
        try {
            const response = await fetch("/oracle-ai/health");
            const data = await response.json();

            if (response.ok && data.success) {
                healthDot.classList.add("good");
                healthDot.classList.remove("bad");
                healthTitle.textContent = "Online";
                healthDetail.textContent = data.message || "Oracle AI chat is available.";
            } else {
                throw new Error(data.error || "Health check failed.");
            }
        } catch (error) {
            healthDot.classList.add("bad");
            healthDot.classList.remove("good");
            healthTitle.textContent = "Offline";
            healthDetail.textContent = error.message;
        }
    }

    async function submitQuestion(event) {
        event.preventDefault();

        const question = questionInput.value.trim();

        if (!question) {
            answerOutput.className = "exai-result-block";
            answerOutput.innerHTML = `
                <div class="exai-alert">
                    Please enter a question before asking the AI.
                </div>
            `;
            return;
        }

        setLoading(true);

        try {
            const response = await fetch("/oracle-ai/ask", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    question,
                    include_sample_rows: includeSampleRowsInput.checked,
                    max_tables: Number(maxTablesInput.value || 50),
                    max_result_rows: Number(maxResultRowsInput.value || 100),
                }),
            });

            const data = await response.json();

            renderAnswer(data);
        } catch (error) {
            renderAnswer({
                success: false,
                question,
                generated_sql: null,
                sql_command_type: null,
                rows: [],
                row_count: 0,
                explanation: "The browser could not complete the Oracle AI request.",
                schema_owner: "UNKNOWN",
                error: error.message,
            });
        } finally {
            setLoading(false);
        }
    }

    async function loadSchemaSummary() {
        setLoading(true);

        try {
            const params = new URLSearchParams({
                include_sample_rows: includeSampleRowsInput.checked ? "true" : "false",
                max_tables: String(Number(maxTablesInput.value || 50)),
            });

            const response = await fetch(`/oracle-ai/schema-summary?${params.toString()}`);
            const data = await response.json();

            schemaOutput.textContent = formatJson(data);
        } catch (error) {
            schemaOutput.textContent = formatJson({
                success: false,
                error: error.message,
            });
        } finally {
            setLoading(false);
        }
    }

    function clearOutput() {
        answerOutput.className = "exai-answer-empty";
        answerOutput.textContent = "Ask a question to see the generated SQL, rows, and explanation.";
        schemaOutput.textContent = "Click \"Load Schema Summary\" to inspect visible schema context.";
        requestIdOutput.textContent = "";
    }

    form.addEventListener("submit", submitQuestion);
    clearButton.addEventListener("click", clearOutput);
    schemaButton.addEventListener("click", loadSchemaSummary);

    checkHealth();
})();

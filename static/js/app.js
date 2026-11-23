/**
 * Real-Time Polling & Survey Platform - Client Application
 * Vanilla JavaScript (Zero Build Step, Zero NPM)
 */

// Toast Notifications
function showToast(message, type = "info", duration = 4000) {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    let icon = "ℹ️";
    if (type === "success") icon = "✅";
    if (type === "warning") icon = "⚠️";
    if (type === "error") icon = "❌";

    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("fade-out");
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ============================================================================
// Poll Creation Form Handler (templates/create.html)
// ============================================================================
function initCreatePollForm() {
    const form = document.getElementById("create-poll-form");
    if (!form) return;

    const questionInput = document.getElementById("question-input");
    const questionCounter = document.getElementById("question-char-count");
    const questionError = document.getElementById("question-error");

    const optionsList = document.getElementById("options-list");
    const btnAddOption = document.getElementById("btn-add-option");
    const optionsBadge = document.getElementById("options-count-badge");
    const optionsError = document.getElementById("options-error");

    const errorBanner = document.getElementById("form-error-banner");
    const btnSubmit = document.getElementById("btn-submit-poll");

    const MIN_OPTIONS = 2;
    const MAX_OPTIONS = 6;

    // Character counter for question
    questionInput.addEventListener("input", () => {
        const len = questionInput.value.length;
        questionCounter.textContent = `${len} / 200`;
        if (len > 0) {
            questionInput.classList.remove("is-invalid");
            questionError.classList.remove("active");
            questionError.textContent = "";
        }
    });

    // Update row numbers and disabled state of remove buttons
    function updateOptionsUI() {
        const rows = optionsList.querySelectorAll(".option-row");
        const count = rows.length;
        optionsBadge.textContent = `${count} of ${MAX_OPTIONS} options`;

        rows.forEach((row, idx) => {
            row.setAttribute("data-index", idx);
            const indexSpan = row.querySelector(".option-index");
            if (indexSpan) indexSpan.textContent = idx + 1;

            const input = row.querySelector(".option-input");
            if (input && !input.getAttribute("data-customized")) {
                input.placeholder = `Option ${idx + 1}`;
            }

            const removeBtn = row.querySelector(".btn-remove-option");
            if (removeBtn) {
                removeBtn.disabled = count <= MIN_OPTIONS;
                removeBtn.setAttribute("aria-label", `Remove option ${idx + 1}`);
            }
        });

        btnAddOption.disabled = count >= MAX_OPTIONS;
        if (count >= MAX_OPTIONS) {
            btnAddOption.textContent = "Maximum Options Reached (6)";
        } else {
            btnAddOption.textContent = "+ Add Another Option";
        }
    }

    // Add option
    btnAddOption.addEventListener("click", () => {
        const currentCount = optionsList.querySelectorAll(".option-row").length;
        if (currentCount >= MAX_OPTIONS) return;

        const row = document.createElement("div");
        row.className = "option-row";
        row.innerHTML = `
            <span class="option-index">${currentCount + 1}</span>
            <input
                type="text"
                class="form-control option-input"
                placeholder="Option ${currentCount + 1}"
                maxlength="100"
                required
            >
            <button type="button" class="btn-icon btn-remove-option" title="Remove option">
                &times;
            </button>
        `;
        optionsList.appendChild(row);

        const newInput = row.querySelector(".option-input");
        newInput.focus();

        updateOptionsUI();
    });

    // Remove option via event delegation
    optionsList.addEventListener("click", (e) => {
        const removeBtn = e.target.closest(".btn-remove-option");
        if (!removeBtn) return;

        const currentCount = optionsList.querySelectorAll(".option-row").length;
        if (currentCount <= MIN_OPTIONS) return;

        const row = removeBtn.closest(".option-row");
        if (row) {
            row.remove();
            updateOptionsUI();
        }
    });

    // Form submission
    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        // Reset errors
        errorBanner.style.display = "none";
        errorBanner.textContent = "";
        questionError.classList.remove("active");
        optionsError.classList.remove("active");

        const question = questionInput.value.trim();
        if (!question) {
            questionInput.classList.add("is-invalid");
            questionError.textContent = "Please enter a poll question.";
            questionError.classList.add("active");
            questionInput.focus();
            return;
        }

        const inputElements = optionsList.querySelectorAll(".option-input");
        const options = [];
        const seen = new Set();
        let hasEmpty = false;
        let hasDuplicate = false;

        inputElements.forEach((inp) => {
            const val = inp.value.trim();
            if (!val) {
                inp.classList.add("is-invalid");
                hasEmpty = true;
            } else {
                inp.classList.remove("is-invalid");
                const lower = val.toLowerCase();
                if (seen.has(lower)) {
                    inp.classList.add("is-invalid");
                    hasDuplicate = true;
                } else {
                    seen.add(lower);
                    options.push(val);
                }
            }
        });

        if (hasEmpty) {
            optionsError.textContent = "All option fields must be filled.";
            optionsError.classList.add("active");
            return;
        }

        if (hasDuplicate) {
            optionsError.textContent = "All options must be unique.";
            optionsError.classList.add("active");
            return;
        }

        if (options.length < MIN_OPTIONS || options.length > MAX_OPTIONS) {
            optionsError.textContent = `Please provide between ${MIN_OPTIONS} and ${MAX_OPTIONS} options.`;
            optionsError.classList.add("active");
            return;
        }

        // Disable submit button and show spinner
        const textContent = btnSubmit.querySelector(".btn-text-content");
        const spinner = btnSubmit.querySelector(".btn-spinner");
        btnSubmit.disabled = true;
        if (textContent) textContent.textContent = "Creating Poll...";
        if (spinner) spinner.style.display = "inline-block";

        try {
            const res = await fetch("/api/polls", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question, options }),
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.error || "Failed to create poll.");
            }

            showToast("Poll created successfully! Redirecting...", "success");
            setTimeout(() => {
                window.location.href = `/poll/${data.id}`;
            }, 500);
        } catch (err) {
            errorBanner.textContent = err.message;
            errorBanner.style.display = "flex";
            btnSubmit.disabled = false;
            if (textContent) textContent.textContent = "Create & Publish Poll";
            if (spinner) spinner.style.display = "none";
        }
    });

    updateOptionsUI();
}

// ============================================================================
// Poll Page Handler (Voting & Real-Time Results Polling)
// ============================================================================
function initPollPage(pollId) {
    const wrapper = document.querySelector(".poll-detail-wrapper");
    if (!wrapper) return;

    let hasVoted = wrapper.dataset.hasVoted === "true";
    let votedOptionId = wrapper.dataset.votedOptionId ? parseInt(wrapper.dataset.votedOptionId, 10) : null;

    const votingSection = document.getElementById("voting-section");
    const resultsSection = document.getElementById("results-section");

    const voteForm = document.getElementById("vote-form");
    const btnSubmitVote = document.getElementById("btn-submit-vote");
    const btnToggleResults = document.getElementById("btn-toggle-results");
    const btnToggleVote = document.getElementById("btn-toggle-vote");

    const duplicateNotice = document.getElementById("duplicate-vote-notice");
    const successNotice = document.getElementById("vote-success-notice");
    const errorNotice = document.getElementById("vote-error-notice");

    const totalVotesCount = document.getElementById("total-votes-count");
    const resultsBarsContainer = document.getElementById("results-bars-container");
    const userVotedBadgeBox = document.getElementById("user-voted-badge-box");
    const userVotedOptionText = document.getElementById("user-voted-option-text");

    let pollInterval = null;

    // Toggle between voting form and results view (if not voted)
    if (btnToggleResults) {
        btnToggleResults.addEventListener("click", () => {
            votingSection.style.display = "none";
            resultsSection.style.display = "block";
            fetchAndRenderResults();
            startLivePolling();
        });
    }

    if (btnToggleVote) {
        btnToggleVote.addEventListener("click", () => {
            if (!hasVoted) {
                resultsSection.style.display = "none";
                votingSection.style.display = "block";
                stopLivePolling();
            }
        });
    }

    // Highlight radio card when selected
    const radioLabels = document.querySelectorAll(".voting-option-item");
    radioLabels.forEach((label) => {
        const radio = label.querySelector(".voting-radio");
        radio.addEventListener("change", () => {
            radioLabels.forEach((l) => l.classList.remove("selected"));
            if (radio.checked) {
                label.classList.add("selected");
            }
        });
    });

    // Submit Vote Handler
    if (voteForm) {
        voteForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            const selectedRadio = voteForm.querySelector('input[name="poll_option"]:checked');
            if (!selectedRadio) {
                showToast("Please select an option to vote.", "warning");
                return;
            }

            const chosenOptionId = parseInt(selectedRadio.value, 10);

            // Button loading state
            btnSubmitVote.disabled = true;
            const btnText = btnSubmitVote.querySelector(".btn-text-content");
            const spinner = btnSubmitVote.querySelector(".btn-spinner");
            if (btnText) btnText.textContent = "Submitting...";
            if (spinner) spinner.style.display = "inline-block";

            errorNotice.style.display = "none";

            try {
                const res = await fetch(`/api/polls/${pollId}/vote`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ option_id: chosenOptionId }),
                });

                const data = await res.json();

                if (res.status === 200) {
                    hasVoted = true;
                    votedOptionId = chosenOptionId;
                    wrapper.dataset.hasVoted = "true";
                    wrapper.dataset.votedOptionId = chosenOptionId;

                    // Immediate visual confirmation
                    successNotice.style.display = "flex";
                    duplicateNotice.style.display = "none";
                    showToast("Your vote has been counted!", "success");

                    // Hide vote form, show results view
                    votingSection.style.display = "none";
                    resultsSection.style.display = "block";
                    if (btnToggleVote) btnToggleVote.style.display = "none";

                    // Update results immediately and start 3-second live updates
                    await fetchAndRenderResults();
                    startLivePolling();
                } else if (res.status === 409) {
                    // Duplicate vote prevention triggered
                    hasVoted = true;
                    wrapper.dataset.hasVoted = "true";

                    duplicateNotice.style.display = "flex";
                    successNotice.style.display = "none";
                    showToast("You have already voted on this poll.", "warning");

                    votingSection.style.display = "none";
                    resultsSection.style.display = "block";
                    if (btnToggleVote) btnToggleVote.style.display = "none";

                    await fetchAndRenderResults();
                    startLivePolling();
                } else {
                    throw new Error(data.error || "Failed to submit vote.");
                }
            } catch (err) {
                errorNotice.textContent = err.message;
                errorNotice.style.display = "flex";
                showToast(err.message, "error");
            } finally {
                btnSubmitVote.disabled = false;
                if (btnText) btnText.textContent = "Submit Vote";
                if (spinner) spinner.style.display = "none";
            }
        });
    }

    // Fetch and render results
    async function fetchAndRenderResults() {
        try {
            const res = await fetch(`/api/polls/${pollId}/results`);
            if (!res.ok) throw new Error("Could not fetch poll results.");

            const data = await res.json();

            // Update total votes
            if (totalVotesCount) {
                totalVotesCount.textContent = data.total_votes;
            }

            // Sync user vote state if backend returns it
            if (data.has_voted) {
                hasVoted = true;
                votedOptionId = data.voted_option_id;
                wrapper.dataset.hasVoted = "true";
                if (votedOptionId) wrapper.dataset.votedOptionId = votedOptionId;
                if (btnToggleVote) btnToggleVote.style.display = "none";
            }

            renderBars(data.results, votedOptionId);

            // Display "You voted for" badge in footer
            if (hasVoted && votedOptionId) {
                const votedItem = data.results.find((item) => item.id === votedOptionId);
                if (votedItem && userVotedBadgeBox && userVotedOptionText) {
                    userVotedOptionText.textContent = votedItem.text;
                    userVotedBadgeBox.style.display = "flex";
                }
            }
        } catch (err) {
            console.error("Error fetching live results:", err);
        }
    }

    // Render horizontal percentage bars with smooth transitions
    function renderBars(results, userChoiceId) {
        if (!resultsBarsContainer) return;

        // Check if bars exist already
        const existingBars = resultsBarsContainer.querySelectorAll(".result-item");

        if (existingBars.length === results.length) {
            // Update existing bars smoothly (preserves transition and avoids DOM thrashing)
            results.forEach((item) => {
                const row = resultsBarsContainer.querySelector(`.result-item[data-option-id="${item.id}"]`);
                if (!row) return;

                const pctText = row.querySelector(".result-pct");
                const countText = row.querySelector(".result-votes-count");
                const fillBar = row.querySelector(".result-bar-fill");

                if (pctText) pctText.textContent = `${item.percentage}%`;
                if (countText) countText.textContent = `(${item.votes} vote${item.votes === 1 ? "" : "s"})`;
                if (fillBar) {
                    fillBar.style.width = `${item.percentage}%`;
                    fillBar.setAttribute("aria-valuenow", item.percentage);
                }

                if (item.id === userChoiceId) {
                    row.classList.add("user-voted");
                    if (!row.querySelector(".result-user-choice-badge")) {
                        const badge = document.createElement("span");
                        badge.className = "result-user-choice-badge";
                        badge.textContent = "Your Choice";
                        row.querySelector(".result-text-group").appendChild(badge);
                    }
                }
            });
        } else {
            // Build bars from scratch
            resultsBarsContainer.innerHTML = "";
            results.forEach((item) => {
                const isUserChoice = item.id === userChoiceId;
                const row = document.createElement("div");
                row.className = `result-item ${isUserChoice ? "user-voted" : ""}`;
                row.setAttribute("data-option-id", item.id);

                row.innerHTML = `
                    <div class="result-item-header">
                        <div class="result-text-group">
                            <span class="result-label">${item.text}</span>
                            ${isUserChoice ? '<span class="result-user-choice-badge">Your Choice</span>' : ""}
                        </div>
                        <div class="result-numbers-group">
                            <span class="result-pct">${item.percentage}%</span>
                            <span class="result-votes-count">(${item.votes} vote${item.votes === 1 ? "" : "s"})</span>
                        </div>
                    </div>
                    <div class="result-bar-track">
                        <div
                            class="result-bar-fill"
                            role="progressbar"
                            aria-valuenow="${item.percentage}"
                            aria-valuemin="0"
                            aria-valuemax="100"
                            style="width: 0%;"
                        ></div>
                    </div>
                `;
                resultsBarsContainer.appendChild(row);

                // Trigger width transition on next animation frame
                requestAnimationFrame(() => {
                    const fill = row.querySelector(".result-bar-fill");
                    if (fill) fill.style.width = `${item.percentage}%`;
                });
            });
        }
    }

    function startLivePolling() {
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(fetchAndRenderResults, 3000);
    }

    function stopLivePolling() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    // Initial load: If user has already voted or results are visible, load results and start polling
    if (hasVoted || resultsSection.style.display !== "none") {
        fetchAndRenderResults();
        startLivePolling();
    }
}

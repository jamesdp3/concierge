const taskListEl = document.getElementById("task-list");
const taskCountEl = document.getElementById("task-count");

const STATE_COLORS = {
    TODO: "#5e81ac",
    NEXT: "#a3be8c",
    WAITING: "#ebcb8b",
    DONE: "#8fbcbb",
    CANCELLED: "#bf616a",
};

const PRIORITY_BADGES = {
    A: { label: "A", color: "#bf616a" },
    B: { label: "B", color: "#d08770" },
    C: { label: "C", color: "#ebcb8b" },
    D: { label: "D", color: "#8888a0" },
};

let allTasks = [];
let filters = { state: "", priority: "" };
let updating = false;

async function fetchTasks() {
    if (updating) return;
    try {
        const res = await fetch("/api/tasks");
        if (!res.ok) return;
        const data = await res.json();
        allTasks = Array.isArray(data) ? data : [];
        render();
    } catch (e) {
        console.error("Failed to fetch tasks:", e);
    }
}

function render() {
    const filtered = allTasks.filter((t) => {
        if (filters.state && t.todo !== filters.state) return false;
        if (filters.priority && t.priority !== filters.priority) return false;
        return true;
    });

    taskCountEl.textContent = filtered.length + " task" + (filtered.length !== 1 ? "s" : "");
    taskListEl.innerHTML = "";

    if (filtered.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = allTasks.length === 0 ? "No tasks yet." : "No tasks match filters.";
        taskListEl.appendChild(empty);
        return;
    }

    filtered.forEach((t) => {
        taskListEl.appendChild(renderTaskCard(t));
    });
}

async function toggleTaskState(taskId, currentState, pill) {
    if (updating) return;
    updating = true;
    const newState = currentState === "DONE" ? "TODO" : "DONE";

    // Optimistic local update
    const task = allTasks.find((t) => t.id === taskId);
    if (task) {
        task.todo = newState;
        render();
    }

    // Fire PATCH (server updates its cache optimistically too)
    try {
        await fetch(`/api/tasks/${taskId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ state: newState }),
        });
    } catch (e) {
        console.error("Failed to update task:", e);
        // Revert on failure
        if (task) {
            task.todo = currentState;
            render();
        }
    } finally {
        updating = false;
    }
}

function renderTaskCard(t) {
    const card = document.createElement("div");
    card.className = "task-card task-card-full";

    const topRow = document.createElement("div");
    topRow.className = "task-card-top";

    // Clickable state pill
    const state = t.todo || "TODO";
    const pill = document.createElement("button");
    pill.className = "task-state task-state-btn";
    pill.textContent = state;
    pill.style.background = STATE_COLORS[state] || "#5e81ac";
    pill.title = state === "DONE" ? "Mark as TODO" : "Mark as DONE";
    pill.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleTaskState(t.id, state, pill);
    });
    topRow.appendChild(pill);

    // Priority badge
    if (t.priority && PRIORITY_BADGES[t.priority]) {
        const pri = document.createElement("span");
        pri.className = "task-priority";
        pri.textContent = t.priority;
        pri.style.borderColor = PRIORITY_BADGES[t.priority].color;
        pri.style.color = PRIORITY_BADGES[t.priority].color;
        topRow.appendChild(pri);
    }

    // Heading
    const heading = document.createElement("span");
    heading.className = "task-heading";
    heading.textContent = t.heading || "Untitled";
    if (state === "DONE") heading.style.textDecoration = "line-through";
    if (state === "DONE") heading.style.opacity = "0.5";
    topRow.appendChild(heading);

    card.appendChild(topRow);

    // Meta row
    const meta = [];
    if (t.deadline) meta.push("\u{1F4C5} " + t.deadline);
    if (t.scheduled) meta.push("\u{1F552} " + t.scheduled.replace(/<|>/g, ""));
    if (t.tags && t.tags.length) meta.push(t.tags.map((tag) => ":" + tag + ":").join(" "));

    if (meta.length) {
        const metaEl = document.createElement("div");
        metaEl.className = "task-meta";
        metaEl.textContent = meta.join("  \u00b7  ");
        card.appendChild(metaEl);
    }

    return card;
}

// Filter pills
document.querySelectorAll(".filter-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
        const group = btn.dataset.filter;
        const value = btn.dataset.value;

        // Update active state within group
        document.querySelectorAll(`.filter-pill[data-filter="${group}"]`).forEach((b) => {
            b.classList.remove("active");
        });
        btn.classList.add("active");

        filters[group] = value;
        render();
    });
});

// Initial fetch + poll
fetchTasks();
setInterval(fetchTasks, 10000);

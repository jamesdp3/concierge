const messagesEl = document.getElementById("messages");
const inputForm = document.getElementById("input-form");
const inputEl = document.getElementById("input");
const typingIndicator = document.getElementById("typing-indicator");
const connectionDot = document.getElementById("connection-status");

let ws = null;
const messageElements = new Map();

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

function connect() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws`);

    ws.onopen = () => {
        connectionDot.className = "status-dot connected";
    };

    ws.onclose = () => {
        connectionDot.className = "status-dot disconnected";
        setTimeout(connect, 2000);
    };

    ws.onerror = () => {
        ws.close();
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleServerMessage(msg);
    };
}

function handleServerMessage(msg) {
    switch (msg.type) {
        case "status_update":
            updateMessageStatus(msg.data.message_id, msg.data.status);
            break;
        case "system_status":
            if (msg.data.status === "typing") {
                typingIndicator.classList.remove("hidden");
            } else {
                typingIndicator.classList.add("hidden");
            }
            break;
        case "response":
            addMessage(msg.data.text, "system");
            typingIndicator.classList.add("hidden");
            break;
        case "task_list":
            addTaskList(msg.data.tasks, msg.data.header);
            typingIndicator.classList.add("hidden");
            break;
        case "error":
            addMessage(msg.data.message, "system");
            typingIndicator.classList.add("hidden");
            break;
    }
}

function addMessage(text, sender, messageId) {
    const el = document.createElement("div");
    el.className = `message ${sender}`;

    const textNode = document.createElement("span");
    textNode.textContent = text;
    el.appendChild(textNode);

    if (sender === "user" && messageId) {
        const badge = document.createElement("span");
        badge.className = "status-badge";
        badge.textContent = "\u2713";
        el.appendChild(badge);
        messageElements.set(messageId, badge);
    }

    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addTaskList(tasks, header) {
    const wrapper = document.createElement("div");
    wrapper.className = "message system task-list-msg";

    if (header) {
        const h = document.createElement("div");
        h.className = "task-list-header";
        h.textContent = header;
        wrapper.appendChild(h);
    }

    if (!tasks || tasks.length === 0) {
        const empty = document.createElement("div");
        empty.className = "task-card";
        empty.textContent = "No tasks found.";
        wrapper.appendChild(empty);
    } else {
        tasks.forEach((t) => {
            wrapper.appendChild(renderTaskCard(t));
        });
    }

    messagesEl.appendChild(wrapper);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderTaskCard(t) {
    const card = document.createElement("div");
    card.className = "task-card";

    // State pill
    const state = t.state || "TODO";
    const pill = document.createElement("span");
    pill.className = "task-state";
    pill.textContent = state;
    pill.style.background = STATE_COLORS[state] || "#5e81ac";
    card.appendChild(pill);

    // Priority badge
    if (t.priority && PRIORITY_BADGES[t.priority]) {
        const pri = document.createElement("span");
        pri.className = "task-priority";
        pri.textContent = t.priority;
        pri.style.borderColor = PRIORITY_BADGES[t.priority].color;
        pri.style.color = PRIORITY_BADGES[t.priority].color;
        card.appendChild(pri);
    }

    // Heading
    const heading = document.createElement("span");
    heading.className = "task-heading";
    heading.textContent = t.heading || "Untitled";
    card.appendChild(heading);

    // Meta row (deadline, scheduled, tags)
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

function updateMessageStatus(messageId, status) {
    const badge = messageElements.get(messageId);
    if (!badge) return;
    if (status === "read") {
        badge.textContent = "\u2713\u2713";
    }
}

function doSend() {
    const text = inputEl.value.trim();
    if (!text) return;

    const messageId = Math.random().toString(36).slice(2, 14);
    addMessage(text, "user", messageId);

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "message", text: text, id: messageId }));
    }

    inputEl.value = "";
    inputEl.style.height = "auto";
}

// Auto-grow textarea
inputEl.addEventListener("input", () => {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px";
});

// Enter to send, Shift+Enter for newline
inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        doSend();
    }
});

// Button click
inputForm.addEventListener("submit", (e) => {
    e.preventDefault();
    doSend();
    return false;
});

connect();

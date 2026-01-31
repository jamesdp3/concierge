const messagesEl = document.getElementById("messages");
const inputForm = document.getElementById("input-form");
const inputEl = document.getElementById("input");
const typingIndicator = document.getElementById("typing-indicator");
const connectionDot = document.getElementById("connection-status");

let ws = null;
const messageElements = new Map();

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
        badge.textContent = "✓";
        el.appendChild(badge);
        messageElements.set(messageId, badge);
    }

    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function updateMessageStatus(messageId, status) {
    const badge = messageElements.get(messageId);
    if (!badge) return;
    if (status === "read") {
        badge.textContent = "✓✓";
    }
}

function sendMessage(text) {
    const messageId = Math.random().toString(36).slice(2, 14);
    addMessage(text, "user", messageId);

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "message", text, id: messageId }));
    }
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
        inputForm.dispatchEvent(new Event("submit"));
    }
});

inputForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text) return;
    sendMessage(text);
    inputEl.value = "";
    inputEl.style.height = "auto";
});

connect();

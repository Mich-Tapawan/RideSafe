document.addEventListener("DOMContentLoaded", () => {
  const HISTORY_KEY = "ridesafe_chat_history";
  const WELCOME_TEXT =
    "Hi — I can help with barangay risk patterns, peak hours, and RideSafe basics. Try asking “What is peak risk in BUCANDALA I?”";

  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send");
  const messages = document.getElementById("chat-messages");
  const status = document.getElementById("chat-status");

  let history = loadHistory();

  function loadHistory() {
    try {
      const raw = sessionStorage.getItem(HISTORY_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length) {
          return parsed;
        }
      }
    } catch (_) {
      /* ignore corrupt session data */
    }
    return [{ role: "assistant", text: WELCOME_TEXT, sources: [] }];
  }

  function saveHistory() {
    try {
      sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    } catch (_) {
      /* quota / private mode */
    }
  }

  function setStatus(text, isError) {
    if (!text) {
      status.hidden = true;
      status.textContent = "";
      return;
    }
    status.hidden = false;
    status.textContent = text;
    status.classList.toggle("chat-status--error", Boolean(isError));
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatAnswer(text) {
    let escaped = escapeHtml(text);
    escaped = escaped.replace(
      /\*\*(.+?)\*\*/g,
      '<strong class="chat-hl">$1</strong>',
    );
    escaped = escaped.replace(
      /(^|[^*])\*([^*\n]+)\*(?!\*)/g,
      "$1<em>$2</em>",
    );
    escaped = escaped.replace(/(^|\n)[-•]\s+([^\n]+)/g, "$1• $2");
    return `<p>${escaped.replace(/\n+/g, "</p><p>")}</p>`;
  }

  function bodyHtmlFor(entry) {
    if (entry.role === "user") {
      return `<p>${escapeHtml(entry.text)}</p>`;
    }
    return formatAnswer(entry.text || "");
  }

  function appendBubble(entry, { scroll = true } = {}) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble chat-bubble--${entry.role}`;
    const body = document.createElement("div");
    body.className = "chat-bubble__body";
    body.innerHTML = bodyHtmlFor(entry);
    bubble.appendChild(body);

    const sources = entry.sources || [];
    if (sources.length) {
      const list = document.createElement("ul");
      list.className = "chat-sources";
      sources.forEach((src) => {
        const li = document.createElement("li");
        li.textContent = src.title || "";
        list.appendChild(li);
      });
      bubble.appendChild(list);
    }

    messages.appendChild(bubble);
    if (scroll) {
      messages.scrollTop = messages.scrollHeight;
    }
  }

  function renderHistory() {
    messages.innerHTML = "";
    history.forEach((entry, index) => {
      appendBubble(entry, { scroll: index === history.length - 1 });
    });
  }

  function pushEntry(entry) {
    history.push(entry);
    saveHistory();
    appendBubble(entry);
  }

  renderHistory();
  saveHistory();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) {
      return;
    }

    pushEntry({ role: "user", text: message, sources: [] });
    input.value = "";
    sendBtn.disabled = true;
    setStatus("Thinking…");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.error || res.statusText || "Request failed");
      }
      pushEntry({
        role: "assistant",
        text: data.answer || "",
        sources: data.sources || [],
      });
      setStatus("");
    } catch (err) {
      const errText = err.message || "Unable to answer right now.";
      setStatus(errText, true);
      pushEntry({ role: "assistant", text: errText, sources: [] });
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send");
  const messages = document.getElementById("chat-messages");
  const status = document.getElementById("chat-status");

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

  function appendBubble(role, htmlBody, sources) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble chat-bubble--${role}`;
    const body = document.createElement("div");
    body.className = "chat-bubble__body";
    body.innerHTML = htmlBody;
    bubble.appendChild(body);

    if (sources && sources.length) {
      const list = document.createElement("ul");
      list.className = "chat-sources";
      sources.forEach((src) => {
        const li = document.createElement("li");
        li.textContent = src.barangay
          ? `${src.title}`
          : src.title;
        list.appendChild(li);
      });
      bubble.appendChild(list);
    }

    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatAnswer(text) {
    const escaped = escapeHtml(text);
    return `<p>${escaped.replace(/\n+/g, "</p><p>")}</p>`;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) {
      return;
    }

    appendBubble("user", `<p>${escapeHtml(message)}</p>`);
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
      appendBubble("assistant", formatAnswer(data.answer || ""), data.sources || []);
      setStatus("");
    } catch (err) {
      setStatus(err.message || "Unable to answer right now.", true);
      appendBubble(
        "assistant",
        `<p>${escapeHtml(err.message || "Unable to answer right now.")}</p>`,
      );
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

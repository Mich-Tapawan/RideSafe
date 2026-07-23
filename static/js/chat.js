document.addEventListener("DOMContentLoaded", () => {
  const HISTORY_KEY = "ridesafe_chat_history";
  const WELCOME_TEXT =
    "Hi — I can help with barangay risk patterns, peak hours, and RideSafe basics. Try asking “What is peak risk in BUCANDALA I?”";

  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send");
  const messages = document.getElementById("chat-messages");
  const status = document.getElementById("chat-status");
  const quotaEl = document.getElementById("chat-quota");
  const adminBtn = document.getElementById("admin-mode-btn");
  const modal = document.getElementById("admin-modal");
  const adminForm = document.getElementById("admin-login-form");
  const adminPassword = document.getElementById("admin-password");
  const adminError = document.getElementById("admin-login-error");
  const adminLogoutBtn = document.getElementById("admin-logout-btn");

  let history = loadHistory();
  let isAdmin = false;

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

  function updateQuotaUi() {
    if (!quotaEl || !adminBtn) {
      return;
    }
    if (isAdmin) {
      quotaEl.textContent = "Admin · unlimited questions";
      quotaEl.classList.add("chat-quota--admin");
      adminBtn.textContent = "Admin ✓";
      adminBtn.classList.add("nav-link--active");
      if (adminLogoutBtn) {
        adminLogoutBtn.hidden = false;
      }
    } else {
      quotaEl.textContent = "Guest · 3 questions / hour";
      quotaEl.classList.remove("chat-quota--admin");
      adminBtn.textContent = "Admin";
      adminBtn.classList.remove("nav-link--active");
      if (adminLogoutBtn) {
        adminLogoutBtn.hidden = true;
      }
    }
  }

  async function refreshStatus() {
    try {
      const res = await fetch("/api/chat/status", { credentials: "same-origin" });
      const data = await res.json().catch(() => ({}));
      isAdmin = Boolean(data.admin);
    } catch (_) {
      isAdmin = false;
    }
    updateQuotaUi();
  }

  function openModal() {
    if (!modal) {
      return;
    }
    modal.hidden = false;
    adminError.hidden = true;
    adminError.textContent = "";
    if (adminPassword) {
      adminPassword.value = "";
      adminPassword.focus();
    }
    updateQuotaUi();
  }

  function closeModal() {
    if (!modal) {
      return;
    }
    modal.hidden = true;
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
  refreshStatus();

  if (adminBtn) {
    adminBtn.addEventListener("click", () => {
      openModal();
    });
  }

  modal?.querySelectorAll("[data-close-modal]").forEach((el) => {
    el.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal && !modal.hidden) {
      closeModal();
    }
  });

  adminForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    adminError.hidden = true;
    try {
      const res = await fetch("/api/chat/admin/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: adminPassword.value }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.error || "Login failed");
      }
      isAdmin = true;
      updateQuotaUi();
      closeModal();
      setStatus("Admin mode enabled — unlimited questions.");
    } catch (err) {
      adminError.textContent = err.message || "Incorrect password.";
      adminError.hidden = false;
    }
  });

  adminLogoutBtn?.addEventListener("click", async () => {
    try {
      await fetch("/api/chat/admin/logout", {
        method: "POST",
        credentials: "same-origin",
      });
    } catch (_) {
      /* ignore */
    }
    isAdmin = false;
    updateQuotaUi();
    closeModal();
    setStatus("Returned to guest mode (3 questions / hour).");
  });

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
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = await res.json().catch(() => ({}));
      if (typeof data.admin === "boolean") {
        isAdmin = data.admin;
        updateQuotaUi();
      }
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

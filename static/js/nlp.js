document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const userInput = document.getElementById("user-input");
  const messageForm = document.getElementById("message-form");
  const chatBox = document.getElementById("chat-box");
  const sendButton = document.querySelector(".send-button");
  const suggestionButtons = document.querySelectorAll(".suggestion-btn");

  // State
  let isLoading = false;

  // Event Listeners
  messageForm.addEventListener("submit", handleSubmit);
  userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  });

  // Handle suggestion buttons
  suggestionButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const suggestion = btn.textContent;
      userInput.value = suggestion;
      handleSubmit();
    });
  });

  /**
   * Handle form submission
   */
  function handleSubmit(e) {
    if (e) e.preventDefault();

    const message = userInput.value.trim();
    if (!message || isLoading) return;

    // Add user message to chat
    addMessageToChat(message, "user");

    // Clear input
    userInput.value = "";
    userInput.focus();

    // Disable send button and show loading state
    setLoading(true);

    // Send to chatbot
    sendMessageToChatbot(message);
  }

  /**
   * Send message to chatbot API
   */
  async function sendMessageToChatbot(userMessage) {
    try {
      // Show typing indicator
      showTypingIndicator();

      const response = await fetch("http://localhost:5000/handlePrompt", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ prompt: userMessage }),
      });

      // Remove typing indicator
      removeTypingIndicator();

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      // Handle response
      if (data.error) {
        addMessageToChat(data.error, "bot");
      } else if (typeof data === "string") {
        addMessageToChat(data, "bot");
      } else if (data.response) {
        addMessageToChat(data.response, "bot");
      } else {
        addMessageToChat(JSON.stringify(data), "bot");
      }

      // Remove welcome message if first message
      const welcomeMessage = document.querySelector(".welcome-message");
      if (welcomeMessage && chatBox.children.length > 1) {
        welcomeMessage.remove();
      }
    } catch (error) {
      console.error("Error:", error);
      removeTypingIndicator();

      // Show error message
      addMessageToChat(
        "Sorry, I encountered an error. Please try again or contact support.",
        "bot"
      );
    } finally {
      setLoading(false);
    }
  }

  /**
   * Add message to chat display
   */
  function addMessageToChat(message, sender) {
    const messageElement = document.createElement("div");
    messageElement.classList.add("message", `${sender}-message`);

    // Escape HTML to prevent XSS
    const safeMessage = escapeHtml(message);
    messageElement.textContent = safeMessage;

    chatBox.appendChild(messageElement);

    // Auto-scroll to latest message
    scrollToBottom();
  }

  /**
   * Show typing indicator
   */
  function showTypingIndicator() {
    const typingContainer = document.createElement("div");
    typingContainer.classList.add("message", "bot-message", "typing-container");
    typingContainer.innerHTML =
      '<div class="typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>';

    chatBox.appendChild(typingContainer);
    scrollToBottom();
  }

  /**
   * Remove typing indicator
   */
  function removeTypingIndicator() {
    const typingContainer = document.querySelector(".typing-container");
    if (typingContainer) {
      typingContainer.remove();
    }
  }

  /**
   * Scroll to bottom of chat
   */
  function scrollToBottom() {
    const messagesWrapper = document.querySelector(".messages-wrapper");
    setTimeout(() => {
      messagesWrapper.scrollTop = messagesWrapper.scrollHeight;
    }, 0);
  }

  /**
   * Set loading state
   */
  function setLoading(loading) {
    isLoading = loading;
    sendButton.disabled = loading;

    if (loading) {
      sendButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    } else {
      sendButton.innerHTML = '<i class="fas fa-paper-plane"></i>';
    }
  }

  /**
   * Escape HTML special characters to prevent XSS
   */
  function escapeHtml(text) {
    const map = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    };
    return text.replace(/[&<>"']/g, (m) => map[m]);
  }

  // Auto-focus input on page load
  userInput.focus();
});

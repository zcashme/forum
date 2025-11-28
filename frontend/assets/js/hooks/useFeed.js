// frontend/assets/js/hooks/useFeed.js
import { renderMessageCard } from "../components/messageCard.js";

export function createFeed({ messagesList, countLabel, searchInput, statusEl }) {
  let allMessages = [];
  let lastId = 0;

  const filterLine = document.getElementById("filterLine");
  const filterLabel = document.getElementById("filterLabel");
  const clearFilterBtn = document.getElementById("clearFilterBtn");

  function setStatus(message, isError = false) {
    if (!statusEl) return;
    statusEl.textContent = message || "";
    statusEl.classList.toggle("error", !!isError);
  }

  function updateCount() {
    const cards = Array.from(messagesList.children);
    const visible = cards.filter((el) => el.style.display !== "none").length;
    countLabel.textContent = visible === 1 ? "1 post" : `${visible} posts`;
  }

  function renderAllMessages() {
    messagesList.innerHTML = "";

    allMessages.forEach((msg) => {
      // messageCard.js should return a DOM element
      const card = renderMessageCard(msg);
      if (card) {
        messagesList.appendChild(card);
      }
    });

    updateCount();
  }

  function applySearchFilter() {
    const term = searchInput.value.trim().toLowerCase();

    Array.from(messagesList.children).forEach((card) => {
      const text = (card.dataset.text || "").toLowerCase();
      const topic = (card.dataset.topic || "").toLowerCase();

      const matches =
        !term || text.includes(term) || (topic && topic.includes(term));

      card.style.display = matches ? "" : "none";
    });

    if (filterLine && filterLabel) {
      if (term) {
        filterLine.style.display = "block";
        filterLabel.textContent = `"${term}"`;
      } else {
        filterLine.style.display = "none";
      }
    }

    updateCount();
  }

  async function loadFeedMessages() {
    try {
      const res = await fetch("/api/messages?limit=50");
      const data = await res.json();
      if (data.status !== "ok") {
        setStatus("Failed to load messages", true);
        return;
      }

      allMessages = data.messages || [];
      lastId = allMessages.reduce((max, m) => Math.max(max, m.id || 0), 0);
      renderAllMessages();
    } catch (e) {
      console.error(e);
      setStatus("Error loading messages", true);
    }
  }

  async function pollNewMessages() {
    try {
      const res = await fetch("/api/messages?limit=50");
      const data = await res.json();
      if (data.status !== "ok") return;

      allMessages = data.messages || [];
      lastId = allMessages.reduce((max, m) => Math.max(max, m.id || 0), 0);
      renderAllMessages();
    } catch (e) {
      // ignore, try again next tick
    }
  }

  async function init() {
    // wire search
    if (searchInput) {
      searchInput.addEventListener("input", applySearchFilter);
    }

    if (clearFilterBtn) {
      clearFilterBtn.addEventListener("click", () => {
        searchInput.value = "";
        applySearchFilter();
      });
    }

    // initial load
    await loadFeedMessages();

    // start polling every 5s
    setInterval(pollNewMessages, 5000);
  }

  return { init, applySearchFilter };
}

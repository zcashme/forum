import { $, setStatus } from "./utils/dom.js";
import { createComposer } from "./hooks/useComposer.js";
import { createFeed } from "./hooks/useFeed.js";

document.addEventListener("DOMContentLoaded", () => {
  const form = $("#messageForm");
  const input = $("#messageInput");
  const sendBtn = $("#sendBtn");
  const statusEl = $("#status");

  const amountInput = $("#amountInput");
  const paymentBody = $("#paymentBody");
  const uriTextEl = $("#uriText");
  const memoTextEl = $("#memoText");
  const openWalletLink = $("#openWalletLink");

  const qr = new QRious({
    element: document.getElementById("qrCanvas"),
    size: 220,
    value: ""
  });

  const composer = createComposer({
    input,
    amountInput,
    paymentBody,
    uriTextEl,
    memoTextEl,
    qr,
    openWalletLink,
    statusEl
  });

  const feed = createFeed({
    messagesList: $("#messagesList"),
    countLabel: $("#countLabel"),
    searchInput: $("#searchInput"),
    statusEl
  });

  // Board funding address modal wiring
  const FORUM_ADDRESS =
    "u13ke4shsnddpr52g0kgjr6gtn604fkgawkezqsht6l2zsrgr7az9698m4q9u0clxrsd6v4d894lut8lqlwlsql32afy2kvmy2zvt320da";

  const toggleBoardInfo = document.getElementById("toggleBoardInfo");
  const boardModal = document.getElementById("boardModal");
  const closeBoardModal = document.getElementById("closeBoardModal");
  const boardAddressText = document.getElementById("boardAddressText");
  const copyAddressBtn = document.getElementById("copyAddressBtn");
  const boardCopyStatus = document.getElementById("boardCopyStatus");
  const boardOpenWalletLink = document.getElementById("boardOpenWalletLink");
  const boardQrCanvas = document.getElementById("boardQrCanvas");

  if (boardAddressText) {
    boardAddressText.textContent = FORUM_ADDRESS;
  }
  if (boardOpenWalletLink) {
    boardOpenWalletLink.href = "zcash:" + FORUM_ADDRESS;
  }

  if (boardQrCanvas) {
    new QRious({
      element: boardQrCanvas,
      size: 180,
      value: "zcash:" + FORUM_ADDRESS
    });
  }

  if (toggleBoardInfo && boardModal) {
    toggleBoardInfo.addEventListener("click", () => {
      boardModal.style.display = "flex";
    });
  }

  if (closeBoardModal && boardModal) {
    closeBoardModal.addEventListener("click", () => {
      boardModal.style.display = "none";
    });
  }

  if (boardModal) {
    boardModal.addEventListener("click", (e) => {
      if (e.target === boardModal) {
        boardModal.style.display = "none";
      }
    });
  }

  if (copyAddressBtn && boardCopyStatus) {
    copyAddressBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(FORUM_ADDRESS);
        boardCopyStatus.textContent = "Copied!";
        boardCopyStatus.classList.remove("error");
        setTimeout(() => {
          boardCopyStatus.textContent = "";
        }, 2000);
      } catch (_) {
        boardCopyStatus.textContent = "Could not copy address";
        boardCopyStatus.classList.add("error");
      }
    });
  }
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) {
      setStatus(statusEl, "Message is empty", true);
      return;
    }
    composer.updatePaymentUI(text);
    setStatus(statusEl, "Payment request generated. Send from your wallet, then wait for the post to appear.");
  });

  feed.init();
});

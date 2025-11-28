import { MAX_MEMO_CHARS, REPLY_PREFIX, FORUM_ADDRESS, DEFAULT_AMOUNT } from "../constants.js";

export function createComposer({ input, amountInput, paymentBody, uriTextEl, memoTextEl, qr, openWalletLink, statusEl }) {
  let replyingToId = null;

  function buildZcashURI(message, amount) {
    const userText = (message || "").slice(0, MAX_MEMO_CHARS);

    let wireText = userText;
    if (replyingToId != null) {
      wireText = `${REPLY_PREFIX}${replyingToId}:${userText}`;
    }

    const b64 = btoa(unescape(encodeURIComponent(wireText)));
    const memoBase64url = b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

    const addr = encodeURIComponent(FORUM_ADDRESS);
    const amt = encodeURIComponent(amount);

    return `zcash:?address=${addr}&amount=${amt}&memo=${memoBase64url}`;
  }

  function updatePaymentUI(message) {
    const amt = amountInput.value || DEFAULT_AMOUNT;
    const uri = buildZcashURI(message, amt);

    qr.value = uri;
    openWalletLink.href = uri;

    const shortBody =
      message.length > 32 ? message.slice(0, 32).trim() + "…" : message || "message";
    uriTextEl.textContent = `forum.zcash.me/(${shortBody})`;

    memoTextEl.textContent = message;
    paymentBody.style.display = "flex";
    setReply(null); // clear reply once we’ve generated
  }

  function setReply(postId) {
    replyingToId = postId;
  }

  function getReplyingToId() {
    return replyingToId;
  }

  return { updatePaymentUI, setReply, getReplyingToId };
}

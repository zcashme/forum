import { truncate, zatsToZec } from "../utils/format.js";
import { CURRENT_USER_ID } from "../constants.js";

export function renderMessageCard(msg, { onReply, onShare, onError }) {
  const card = document.createElement("div");
  card.className = "msg-card";

  const zec = zatsToZec(msg.amount_zats);

  if (zec >= 0.002) card.classList.add("tier-3");
  else if (zec >= 0.00012) card.classList.add("tier-2");
  else if (zec > 0.000015) card.classList.add("tier-1");

  if (!msg.text || msg.text === "[deleted]") {
    return null;
  }

  const hue = (msg.id * 137) % 360;
  const avatarStyle = `background: linear-gradient(135deg, hsl(${hue}, 60%, 50%), hsl(${(hue + 40) % 360}, 60%, 50%));`;

  card.innerHTML = `
    <div class="post-header">
      <div class="post-avatar" style="${avatarStyle}"></div>
      <div class="post-info">
        <div class="post-author-line">
          <span class="post-author">Anonymous User</span>
        </div>
        <div class="post-time">${msg.created_at || ""}</div>
      </div>
    </div>
    <div class="post-body"></div>
    <div class="post-footer">
      <span class="verified-badge">
        <svg viewBox="0 0 24 24">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10
                  10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5
                  1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
        </svg>
        Verified Memo
      </span>
      <span>Zcash Network</span>
    </div>
    <div class="post-actions">
      <button type="button" class="post-action-btn action-like">
        <span class="post-action-icon">❤</span>
        <span class="post-like-count">0</span>
      </button>
      <button type="button" class="post-action-btn action-comment">
        <span class="post-action-icon">💬</span>
        <span>Comment</span>
      </button>
      <button type="button" class="post-action-btn action-share">
        <span class="post-action-icon">↗</span>
        <span>Share</span>
      </button>
    </div>
    <div class="comment-list"></div>
  `;

  card.querySelector(".post-body").textContent = msg.text;
  card.dataset.text = msg.text || "";

  const likeBtn = card.querySelector(".action-like");
  const likeCountEl = card.querySelector(".post-like-count");
  const commentBtn = card.querySelector(".action-comment");
  const shareBtn = card.querySelector(".action-share");

  const initialLikes = typeof msg.likes === "number" ? msg.likes : 0;
  likeCountEl.textContent = initialLikes;

  likeBtn.addEventListener("click", async () => {
    if (!CURRENT_USER_ID) {
      onError?.("You must be signed in to like posts");
      return;
    }

    likeBtn.disabled = true;
    try {
      const res = await fetch(`/api/messages/${msg.id}/like`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: CURRENT_USER_ID })
      });
      const data = await res.json();
      if (data.status !== "ok") throw new Error(data.error || "like failed");
      likeCountEl.textContent = data.likes;
      likeBtn.classList.toggle("liked", data.liked);
    } catch (err) {
      onError?.("Could not update like");
    } finally {
      likeBtn.disabled = false;
    }
  });

  commentBtn.addEventListener("click", () => {
    onReply?.(msg);
  });

  shareBtn.addEventListener("click", async () => {
    const shareUrl = window.location.origin + "/" + msg.id;
    try {
      if (navigator.share) {
        await navigator.share({
          title: "forum.zcash.me",
          text: truncate(msg.text, 100),
          url: shareUrl
        });
      } else {
        await navigator.clipboard.writeText(shareUrl);
        onError?.("Post link copied to clipboard");
      }
    } catch (_) {
      // ignore
    }
  });

  return card;
}

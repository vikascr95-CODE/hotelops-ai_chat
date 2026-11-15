const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const messages = document.getElementById("messages");
const welcome = document.getElementById("welcome");
const sendButton = document.getElementById("sendButton");
const conversationList = document.getElementById("conversationList");
let conversationId = null;

function addMessage(role, content, tasks = []) {
  welcome.style.display = "none";
  const row = document.createElement("div");
  row.className = `message ${role}`;
  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.textContent = role === "assistant" ? "✦" : "G";
  const body = document.createElement("div");
  body.className = "bubble";
  body.textContent = content;
  row.append(avatar, body);
  if (tasks.length) {
    const chips = document.createElement("div");
    chips.className = "task-chips";
    tasks.forEach(task => {
      const chip = document.createElement("div");
      chip.className = "task-chip";
      chip.innerHTML = `<strong>${escapeHtml(task.id)}</strong> · ${escapeHtml(task.department)} · ${escapeHtml(task.priority)}`;
      chips.appendChild(chip);
    });
    body.appendChild(chips);
  }
  messages.appendChild(row);
  document.querySelector(".chat-area").scrollTop = document.querySelector(".chat-area").scrollHeight;
}
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function showTyping() {
  const el = document.createElement("div");
  el.id = "typing";
  el.className = "typing";
  el.textContent = "HotelOps AI is thinking…";
  messages.appendChild(el);
}
async function sendMessage(text) {
  const message = (text || input.value).trim();
  if (!message || sendButton.disabled) return;
  addMessage("user", message);
  input.value = "";
  input.style.height = "35px";
  sendButton.disabled = true;
  showTyping();
  try {
    const res = await fetch("/api/chat", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        message, conversation_id: conversationId,
        guest_name: document.getElementById("guestName").value.trim() || null,
        room_number: document.getElementById("roomNumber").value.trim() || null
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "The request could not be processed.");
    conversationId = data.conversation_id;
    document.getElementById("typing")?.remove();
    addMessage("assistant", data.reply, data.tasks || []);
    loadConversations();
  } catch (err) {
    document.getElementById("typing")?.remove();
    addMessage("assistant", `Sorry, I couldn't process that message. ${err.message}`);
  } finally {
    sendButton.disabled = false;
    input.focus();
  }
}
form.addEventListener("submit", e => { e.preventDefault(); sendMessage(); });
input.addEventListener("input", () => { input.style.height = "35px"; input.style.height = Math.min(input.scrollHeight,120) + "px"; });
input.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
document.querySelectorAll(".suggestion").forEach(btn => btn.addEventListener("click", () => sendMessage(btn.dataset.message)));
document.getElementById("newChat").addEventListener("click", () => {
  conversationId = null; messages.innerHTML = ""; welcome.style.display = "block";
  document.querySelectorAll(".conversation-item").forEach(el => el.classList.remove("active"));
  input.focus();
});
async function loadConversations() {
  try {
    const res = await fetch("/api/conversations");
    const items = await res.json();
    conversationList.innerHTML = "";
    items.forEach(item => {
      const el = document.createElement("div");
      el.className = "conversation-item" + (item.id === conversationId ? " active" : "");
      el.textContent = item.last_message || "New conversation";
      el.title = el.textContent;
      el.addEventListener("click", () => openConversation(item.id));
      conversationList.appendChild(el);
    });
    if (!items.length) conversationList.innerHTML = '<div class="muted side-empty">Your conversations will appear here.</div>';
  } catch {}
}
async function openConversation(id) {
  try {
    const res = await fetch(`/api/conversations/${id}/messages`);
    if (!res.ok) return;
    const items = await res.json();
    conversationId = id; messages.innerHTML = ""; welcome.style.display = "none";
    items.forEach(item => addMessage(item.role, item.content));
    loadConversations();
  } catch {}
}
loadConversations();

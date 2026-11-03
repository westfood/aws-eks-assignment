"use strict";

const form = document.getElementById("message-form");
const messageInput = document.getElementById("message");
const saveButton = document.getElementById("save-button");
const refreshButton = document.getElementById("refresh-button");
const feedback = document.getElementById("form-feedback");
const list = document.getElementById("messages");
const caption = document.getElementById("list-caption");

async function requestJSON(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, { ...options, signal: controller.signal, cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "The database is temporarily unavailable. Please try again.");
    return data;
  } finally {
    clearTimeout(timer);
  }
}

function emptyState(title, detail) {
  list.replaceChildren();
  const box = document.createElement("div");
  box.className = "empty-state";
  const heading = document.createElement("strong");
  heading.textContent = title;
  const body = document.createElement("span");
  body.textContent = detail;
  box.append(heading, body);
  list.append(box);
}

async function checkDatabase() {
  const started = performance.now();
  const dot = document.getElementById("status-dot");
  const status = document.getElementById("database-status");
  try {
    await requestJSON("/readyz");
    dot.className = "status-dot ready";
    status.textContent = "Database connected";
    document.getElementById("response-time").textContent = `${Math.round(performance.now() - started)} ms last check`;
  } catch {
    dot.className = "status-dot unavailable";
    status.textContent = "Database unavailable";
    document.getElementById("response-time").textContent = "";
  }
}

async function loadMessages() {
  refreshButton.disabled = true;
  try {
    const data = await requestJSON("/api/messages");
    list.replaceChildren();
    if (data.messages.length === 0) {
      caption.textContent = "No messages saved yet";
      emptyState("The first message is yours.", "Save a message to verify a database write and read.");
      return;
    }
    caption.textContent = `${data.messages.length} most recent ${data.messages.length === 1 ? "message" : "messages"}`;
    for (const message of data.messages) {
      const card = document.createElement("article");
      card.className = "message-card";
      const text = document.createElement("p");
      // Stored user input is always text, never interpreted as HTML.
      text.textContent = message.body;
      const details = document.createElement("div");
      details.className = "message-details";
      const identity = document.createElement("span");
      identity.textContent = `MESSAGE ${message.id}`;
      const time = document.createElement("time");
      time.dateTime = message.created_at;
      time.textContent = new Date(message.created_at).toLocaleString();
      details.append(identity, time);
      card.append(text, details);
      list.append(card);
    }
  } catch {
    caption.textContent = "Messages could not be loaded";
    emptyState("The database is unavailable.", "Use Refresh to retry the database connection.");
  } finally {
    refreshButton.disabled = false;
  }
}

messageInput.addEventListener("input", () => {
  document.getElementById("character-count").textContent = `${messageInput.value.length} / 512`;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = messageInput.value.trim();
  if (!body) {
    feedback.textContent = "Write a message before saving.";
    feedback.className = "form-feedback error";
    return;
  }
  saveButton.disabled = true;
  feedback.textContent = "Saving…";
  feedback.className = "form-feedback";
  try {
    await requestJSON("/api/messages", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body }) });
    messageInput.value = "";
    document.getElementById("character-count").textContent = "0 / 512";
    feedback.textContent = "Saved. Your message was written to the database.";
    await Promise.all([loadMessages(), checkDatabase()]);
  } catch (error) {
    feedback.textContent = error.name === "AbortError" ? "The request timed out. Refresh the list before trying again." : error.message;
    feedback.className = "form-feedback error";
    await checkDatabase();
  } finally {
    saveButton.disabled = false;
  }
});

refreshButton.addEventListener("click", () => Promise.all([loadMessages(), checkDatabase()]));
Promise.all([loadMessages(), checkDatabase()]);

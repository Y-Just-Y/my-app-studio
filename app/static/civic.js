"use strict";

const root = document.querySelector("[data-civic-chat]");
if (root) {
  const form = root.querySelector("[data-question-form]");
  const question = form.querySelector("textarea");
  const transcript = root.querySelector("[data-transcript]");
  const status = root.querySelector("[data-chat-status]");
  const submit = form.querySelector("button[type=submit]");

  function paragraph(parent, text, className) {
    const element = document.createElement("p");
    element.textContent = text;
    if (className) element.className = className;
    parent.append(element);
    return element;
  }

  function message(role, text) {
    const item = document.createElement("li");
    item.className = "chat-message " + role;
    paragraph(item, role === "reader" ? "You" : "Newark Civic Pulse", "message-author");
    paragraph(item, text, "message-text");
    transcript.append(item);
    return item;
  }

  function evidence(parent, sources) {
    if (!sources.length) return;
    const list = document.createElement("ol");
    list.className = "citation-list";
    for (const source of sources) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      const address = new URL(source.url);
      if (address.protocol !== "https:") continue;
      link.href = address.href;
      link.textContent = source.title;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      item.append(link);
      paragraph(item, source.text, "source-excerpt");
      paragraph(item, "Source passage: " + source.chunk_id + " · Retrieved " + source.fetched_at, "source-line");
      list.append(item);
    }
    parent.append(list);
  }

  root.querySelectorAll("[data-question]").forEach((button) => {
    button.addEventListener("click", () => {
      question.value = button.dataset.question;
      question.focus();
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const text = question.value.trim();
    if (text.length < 3) return;
    submit.disabled = true;
    status.textContent = "Checking the saved records…";
    message("reader", text);
    try {
      const tokenResponse = await fetch("/api/csrf", { credentials: "same-origin" });
      if (!tokenResponse.ok) throw new Error("Could not start a secure question. Refresh and try again.");
      const token = await tokenResponse.json();
      const response = await fetch("/api/civic/chat", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": token.csrf_token },
        body: JSON.stringify({ question: text, mode: form.elements.mode.value }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "That request could not be completed.");
      const item = message("assistant", result.answer);
      paragraph(item, result.mode === "ai" ? "AI-generated · " + result.model + " · " + result.retrieval + " retrieval" : "Source search · no AI-generated answer", "message-mode");
      evidence(item, result.sources || []);
      question.value = "";
      status.textContent = "Evidence checked against the saved snapshot.";
    } catch (error) {
      message("assistant", error.message || "The request failed. Please try again.");
      status.textContent = "Your question is still in the field so you can retry.";
    } finally {
      submit.disabled = false;
      question.focus();
    }
  });
}

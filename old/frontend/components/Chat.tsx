"use client";

import { useRef, useState } from "react";
import { Citation, streamChat } from "../lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const sessionId = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function send() {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

    try {
      for await (const ev of streamChat(text, sessionId.current, token, controller.signal)) {
        if (ev.event === "token") {
          setMessages((m) => patchLast(m, (a) => ({ ...a, content: a.content + ev.data.text })));
        } else if (ev.event === "citations") {
          setMessages((m) => patchLast(m, (a) => ({ ...a, citations: ev.data.items })));
        } else if (ev.event === "done") {
          sessionId.current = ev.data.session_id;
        } else if (ev.event === "error") {
          setMessages((m) => patchLast(m, (a) => ({ ...a, content: a.content || `⚠ ${ev.data.detail}` })));
        }
      }
    } catch {
      // aborted or network error; leave partial content
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function stop() {
    abortRef.current?.abort();
  }

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto p-4">
      <h1 className="text-xl font-semibold mb-4">Product Recommender</h1>
      <div className="flex-1 overflow-y-auto space-y-3">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <div className={`inline-block rounded-lg px-3 py-2 ${m.role === "user" ? "bg-blue-600 text-white" : "bg-gray-100"}`}>
              {m.content || (streaming && i === messages.length - 1 ? "…" : "")}
              {m.citations && m.citations.length > 0 && (
                <ul className="mt-2 text-xs text-gray-500 list-disc pl-4">
                  {m.citations.map((c, j) => <li key={j}>{c.product_name}</li>)}
                </ul>
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-2 mt-4">
        <input
          className="flex-1 border rounded-lg px-3 py-2"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about a product…"
          disabled={streaming}
        />
        {streaming ? (
          <button className="bg-red-600 text-white rounded-lg px-4" onClick={stop}>Stop</button>
        ) : (
          <button className="bg-blue-600 text-white rounded-lg px-4" onClick={send}>Send</button>
        )}
      </div>
    </div>
  );
}

function patchLast(messages: Message[], fn: (m: Message) => Message): Message[] {
  const copy = messages.slice();
  copy[copy.length - 1] = fn(copy[copy.length - 1]);
  return copy;
}

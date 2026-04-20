import React, { useState, useRef, useEffect } from 'react';
import { Bot, Send, User } from 'lucide-react';

const MAX_CHARS = 500;

/**
 * Chat Component – AI Concierge
 *
 * Features:
 * - Stable message IDs via `crypto.randomUUID()` (no array-index keys)
 * - AbortController cleanup on unmount to prevent state updates on dead components
 * - Character counter to mirror backend MAX_MESSAGE_LENGTH
 * - Escape key clears the input field
 * - Surfaces HTTP error detail from the backend in the chat bubble
 *
 * @returns {JSX.Element}
 */

export default function Chat() {
  const [messages, setMessages] = useState([
    { id: crypto.randomUUID(), role: 'bot', text: 'Hello! I am your AI Stadium Concierge. Ask me about gates, transport, food, or first aid.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endOfMessagesRef = useRef(null);
  const abortRef = useRef(null);
  // Track whether the component is still mounted to avoid state updates after unmount.
  const mountedRef = useRef(true);

  // Cleanup any in-flight request on unmount and mark component as dead.
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

  const scrollToBottom = () => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    const userMsg = trimmed;
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'user', text: userMsg }]);
    setInput('');
    setLoading(true);

    abortRef.current = new AbortController();

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg }),
        signal: abortRef.current.signal,
      });

      const data = await res.json();
      if (res.ok) {
        setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'bot', text: data.reply }]);
      } else {
        const detail = data?.detail ?? `Error ${res.status}`;
        setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'bot', text: `⚠️ ${detail}` }]);
      }
    } catch (err) {
      if (err.name === 'AbortError') return; // Component unmounted – suppress
      console.error(err);
      if (mountedRef.current) {
        setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'bot', text: '⚠️ Network error. Please try again.' }]);
      }
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  };

  /** Clear input on Escape key */
  const handleKeyDown = (e) => {
    if (e.key === 'Escape') setInput('');
  };

  return (
    <div className="glass flex flex-col h-[650px] overflow-hidden shadow-2xl">
      <div className="p-5 border-b border-white/5 bg-black/20 flex items-center gap-3">
        <Bot className="h-7 w-7 text-brandAccent drop-shadow-md" aria-hidden="true" />
        <h2 className="text-xl font-semibold tracking-wide">AI Concierge</h2>
      </div>
      
      <div 
        className="flex-1 overflow-y-auto p-5 space-y-5"
        role="log"
        aria-label="Chat messages"
        aria-live="polite"
      >
        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} animate-slide-up`}>
            <div className={`max-w-[85%] p-4 rounded-2xl flex items-start gap-4 shadow-sm ${
              m.role === 'user' ? 'bg-gradient-to-br from-blue-500 to-brandAccent text-white rounded-tr-none' : 'bg-white/10 backdrop-blur-md text-gray-100 border border-white/5 rounded-tl-none'
            }`}>
              {m.role === 'bot' && <Bot className="h-5 w-5 mt-0.5 flex-shrink-0 opacity-80" aria-hidden="true" />}
              <p className="text-[15px] leading-relaxed drop-shadow-sm">{m.text}</p>
              {m.role === 'user' && <User className="h-5 w-5 mt-0.5 flex-shrink-0 opacity-80" aria-hidden="true" />}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start animate-fade-in">
            <div className="bg-white/5 backdrop-blur-md border border-white/5 text-gray-400 rounded-2xl rounded-tl-none p-4 text-sm flex gap-1.5 items-center">
              <span className="w-2 h-2 rounded-full bg-brandAccent/60 animate-pulse"></span>
              <span className="w-2 h-2 rounded-full bg-brandAccent/60 animate-pulse [animation-delay:150ms]"></span>
              <span className="w-2 h-2 rounded-full bg-brandAccent/60 animate-pulse [animation-delay:300ms]"></span>
            </div>
          </div>
        )}
        <div ref={endOfMessagesRef} />
      </div>

      <form onSubmit={handleSubmit} className="p-4 border-t border-white/5 flex flex-col gap-2 bg-black/40 backdrop-blur-md">
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value.slice(0, MAX_CHARS))}
            onKeyDown={handleKeyDown}
            placeholder="Ask about gates, food, transport… (Esc to clear)"
            className="flex-1 bg-black/50 border border-white/10 rounded-xl px-5 py-3 text-[15px] text-white placeholder:text-gray-500 focus:outline-none focus:border-brandAccent focus:ring-1 focus:ring-brandAccent transition-all shadow-inner"
            aria-label="Type your message to the AI Concierge"
            maxLength={MAX_CHARS}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="bg-gradient-to-r from-blue-600 to-brandAccent text-white p-3 rounded-xl hover:scale-105 hover:shadow-[0_0_15px_rgba(59,130,246,0.4)] disabled:opacity-50 disabled:hover:scale-100 disabled:cursor-not-allowed transition-all"
            aria-label="Send message"
          >
            <Send className="h-5 w-5 drop-shadow-md" aria-hidden="true" />
          </button>
        </div>
        <div className={`text-right text-xs pr-1 ${
          input.length >= MAX_CHARS ? 'text-red-400' : 'text-gray-600'
        }`} aria-live="polite" aria-atomic="true">
          {input.length}/{MAX_CHARS}
        </div>
      </form>
    </div>
  );
}

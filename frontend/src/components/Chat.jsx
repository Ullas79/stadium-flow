import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Bot, Send, User } from 'lucide-react';

const MAX_CHARS = 500;

/**
 * Chat Component – AI Concierge
 *
 * Features:
 * - Stable message IDs via `crypto.randomUUID()` (no array-index keys)
 * - AbortController cleanup on unmount to prevent state updates on dead components
 * - Character counter to mirror backend MAX_MESSAGE_LENGTH
 * - Escape key clears the input field; Ctrl+Enter submits the message
 * - Surfaces HTTP error detail from the backend in the chat bubble
 * - Message timestamps displayed with accessible `<time>` elements
 * - Typing indicator with `aria-live="assertive"` for screen readers
 * - Focus returns to input after bot replies
 *
 * @returns {JSX.Element}
 */

const playNotificationSound = () => {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gainNode = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(800, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(1200, ctx.currentTime + 0.1);
    gainNode.gain.setValueAtTime(0.1, ctx.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
    osc.connect(gainNode);
    gainNode.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.5);
  } catch (e) {
    // Ignore audio errors (e.g. strict autoplay policies)
  }
};

export default function Chat() {
  const [messages, setMessages] = useState([
    {
      id: crypto.randomUUID(),
      role: 'bot',
      text: 'Hello! I am your AI Stadium Concierge. Ask me about gates, transport, food, or first aid.',
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endOfMessagesRef = useRef(null);
  const inputRef = useRef(null);
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

  /** Format a Date as HH:MM for display. */
  const formatTimestamp = (date) =>
    date ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

  /** ISO 8601 string for the <time> datetime attribute. */
  const isoTimestamp = (date) => date?.toISOString() ?? '';

  const sendMessage = useCallback(async (text) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const timestamp = new Date();
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'user', text: trimmed, timestamp }]);
    setInput('');
    setLoading(true);

    abortRef.current = new AbortController();

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed }),
        signal: abortRef.current.signal,
      });

      const data = await res.json();
      const botTimestamp = new Date();
      if (res.ok) {
        setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'bot', text: data.reply, timestamp: botTimestamp }]);
        playNotificationSound();
      } else {
        const detail = data?.detail ?? `Error ${res.status}`;
        setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'bot', text: `⚠️ ${detail}`, timestamp: botTimestamp }]);
      }
    } catch (err) {
      if (err.name === 'AbortError') return; // Component unmounted – suppress
      console.error(err);
      if (mountedRef.current) {
        setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'bot', text: '⚠️ Network error. Please try again.', timestamp: new Date() }]);
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
        // Return focus to input after the bot replies
        inputRef.current?.focus();
      }
    }
  }, [loading]);

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      setInput('');
    } else if (e.key === 'Enter' && e.ctrlKey) {
      e.preventDefault();
      sendMessage(input);
    }
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
            <div className={`max-w-[85%] p-4 rounded-2xl flex flex-col gap-1 shadow-sm ${
              m.role === 'user'
                ? 'bg-gradient-to-br from-blue-500 to-brandAccent text-white rounded-tr-none'
                : 'bg-white/10 backdrop-blur-md text-gray-100 border border-white/5 rounded-tl-none'
            }`}>
              <div className="flex items-start gap-4">
                {m.role === 'bot' && <Bot className="h-5 w-5 mt-0.5 flex-shrink-0 opacity-80" aria-hidden="true" />}
                <p className="text-[15px] leading-relaxed drop-shadow-sm">{m.text}</p>
                {m.role === 'user' && <User className="h-5 w-5 mt-0.5 flex-shrink-0 opacity-80" aria-hidden="true" />}
              </div>
              {m.timestamp && (
                <time
                  dateTime={isoTimestamp(m.timestamp)}
                  className={`text-[11px] opacity-50 self-end`}
                  aria-label={`Sent at ${formatTimestamp(m.timestamp)}`}
                >
                  {formatTimestamp(m.timestamp)}
                </time>
              )}
            </div>
          </div>
        ))}

        {/* Typing indicator with assertive aria-live so screen readers announce it immediately */}
        {loading && (
          <div
            className="flex justify-start animate-fade-in"
            aria-live="assertive"
            aria-label="AI Concierge is typing"
          >
            <div className="bg-white/5 backdrop-blur-md border border-white/5 text-gray-400 rounded-2xl rounded-tl-none p-4 text-sm flex gap-1.5 items-center">
              <span className="w-2 h-2 rounded-full bg-brandAccent/60 animate-pulse"></span>
              <span className="w-2 h-2 rounded-full bg-brandAccent/60 animate-pulse [animation-delay:150ms]"></span>
              <span className="w-2 h-2 rounded-full bg-brandAccent/60 animate-pulse [animation-delay:300ms]"></span>
            </div>
          </div>
        )}
        <div ref={endOfMessagesRef} />
      </div>

      <form onSubmit={handleSubmit} className="p-4 border-t border-white/5 flex flex-col gap-3 bg-black/40 backdrop-blur-md">
        {messages.length === 1 && (
          <div className="flex gap-2 pb-1 overflow-x-auto scrollbar-hide">
            {['🍔 Where is the food counter?', '🏃 Best exit gate?', '🚇 Metro wait time?', '🚑 First Aid'].map(promptText => (
              <button
                key={promptText}
                type="button"
                onClick={() => sendMessage(promptText)}
                className="whitespace-nowrap px-3 py-1.5 rounded-lg bg-white/5 hover:bg-brandAccent/20 border border-white/10 text-[13px] text-brandAccent transition-all shadow-sm"
              >
                {promptText}
              </button>
            ))}
          </div>
        )}
        <div className="flex gap-3">
          <input
            ref={inputRef}
            id="chat-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value.slice(0, MAX_CHARS))}
            onKeyDown={handleKeyDown}
            placeholder="Ask about gates, food, transport… (Ctrl+Enter to send, Esc to clear)"
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
        <div
          className={`text-right text-xs pr-1 ${input.length >= MAX_CHARS ? 'text-red-400' : 'text-gray-600'}`}
          aria-live="polite"
          aria-atomic="true"
        >
          {input.length}/{MAX_CHARS}
        </div>
      </form>
    </div>
  );
}

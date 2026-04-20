import React from 'react';
import Dashboard from './components/Dashboard';
import Chat from './components/Chat';
import { Activity } from 'lucide-react';

/**
 * Main Application Component
 * Wraps the Dashboard and Chat sections.
 */
function App() {
  return (
    <div className="min-h-screen p-4 md:p-8 font-sans animate-fade-in relative z-10">
      <header className="mb-10 flex flex-col md:flex-row items-start md:items-center justify-between border-b border-white/5 pb-6 gap-4">
        <div className="flex items-center gap-4 group cursor-default">
          <div className="p-2.5 bg-brandAccent/10 rounded-xl border border-brandAccent/20 group-hover:bg-brandAccent/20 transition-colors">
            <Activity className="h-7 w-7 text-brandAccent group-hover:scale-110 transition-transform duration-300" aria-hidden="true" />
          </div>
          <h1 className="text-4xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-500 dropping-shadow">
            CrowdSync
          </h1>
        </div>
        <nav aria-label="Main Navigation">
          <ul className="flex gap-6 text-[15px] font-medium">
            <li><a href="#dashboard" className="text-gray-400 hover:text-white transition-colors" aria-label="Go to Dashboard">Dashboard</a></li>
            <li><a href="#chat" className="text-gray-400 hover:text-white transition-colors" aria-label="Go to AI Concierge">AI Concierge</a></li>
          </ul>
        </nav>
      </header>
      
      <main className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <section className="lg:col-span-2 space-y-8 animate-slide-up" id="dashboard" aria-label="Stadium Dashboard">
          <Dashboard />
        </section>
        
        <aside className="lg:col-span-1 animate-slide-up [animation-delay:150ms]" id="chat" aria-label="AI Concierge Chat">
          <Chat />
        </aside>
      </main>
    </div>
  );
}

export default App;

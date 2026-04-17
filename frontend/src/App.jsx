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
    <div className="min-h-screen p-4 md:p-8 font-sans">
      <header className="mb-8 flex items-center justify-between border-b border-gray-800 pb-4">
        <div className="flex items-center gap-3">
          <Activity className="h-8 w-8 text-brandAccent" aria-hidden="true" />
          <h1 className="text-3xl font-bold tracking-tight text-white">CrowdSync</h1>
        </div>
        <nav aria-label="Main Navigation">
          <ul className="flex gap-4 text-sm font-medium">
            <li><a href="#" className="text-gray-400 hover:text-white transition-colors" aria-label="Go to Dashboard">Dashboard</a></li>
            <li><a href="#chat" className="text-gray-400 hover:text-white transition-colors" aria-label="Go to AI Concierge">AI Concierge</a></li>
          </ul>
        </nav>
      </header>
      
      <main className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <section className="lg:col-span-2 space-y-8" aria-label="Stadium Dashboard">
          <Dashboard />
        </section>
        
        <aside className="lg:col-span-1" id="chat" aria-label="AI Concierge Chat">
          <Chat />
        </aside>
      </main>
    </div>
  );
}

export default App;

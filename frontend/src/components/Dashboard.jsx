import React, { useState, useEffect, useCallback } from 'react';
import { Map, Train, Ticket, AlertCircle, RefreshCw, Clock } from 'lucide-react';

/**
 * Dashboard Component
 * Polls the backend every 30 s (matching cache TTL) for stadium gate
 * statuses and transport wait times, then renders them with colour-coded
 * density cards and inline transport chips.
 *
 * @returns {JSX.Element}
 */
export default function Dashboard() {
  const [data, setData] = useState({ gates: [], transport: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  /**
   * Fetch current status from the backend.
   * Memoised so useEffect dep is stable.
   * @param {boolean} isRetry – pass true when the user clicks Retry to
   *   restore the loading spinner.
   */
  const fetchStatus = useCallback(async (isRetry = false) => {
    if (isRetry) setLoading(true);
    try {
      const res = await fetch('/api/stadium/status');
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const json = await res.json();
      setData(json.data);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      console.error('Failed to fetch stadium status', err);
      setError('Could not reach the server. Retrying…');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // Poll every 30 s to match cache TTL
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const formatTime = (date) =>
    date ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';

  const getStatusColor = (status) => {
    switch(status) {
      case 'Green': return 'bg-green-500/10 text-green-300 border-green-500/30 shadow-[0_0_20px_rgba(34,197,94,0.15)]';
      case 'Yellow': return 'bg-yellow-500/10 text-yellow-300 border-yellow-500/30 shadow-[0_0_20px_rgba(234,179,8,0.15)]';
      case 'Red': return 'bg-red-500/10 text-red-300 border-red-500/30 shadow-[0_0_20px_rgba(239,68,68,0.15)]';
      default: return 'bg-gray-500/10 text-gray-400 border-gray-500/30';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold flex items-center gap-2">
          <Map className="h-6 w-6 text-brandAccent" aria-hidden="true" />
          Gate Density Monitor
        </h2>
        {lastUpdated && (
          <span className="flex items-center gap-1.5 text-xs text-gray-500" aria-live="polite">
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            Updated {formatTime(lastUpdated)}
          </span>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-400" role="status" aria-live="assertive">
          <AlertCircle className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
          <span className="text-sm">{error}</span>
          <button onClick={() => fetchStatus(true)} className="ml-auto flex items-center gap-1.5 text-xs underline hover:no-underline" aria-label="Retry fetching stadium status">
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" /> Retry
          </button>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-pulse-slow" role="status" aria-live="polite">
          {[1,2,3,4].map(idx => (
            <div key={idx} className="h-[150px] glass rounded-2xl skeleton-bg"></div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data.gates.map((gate) => (
            <div
              key={gate.id}
              className={`p-6 rounded-2xl flex flex-col gap-2 transition-all duration-300 hover:-translate-y-1 hover:brightness-110 backdrop-blur-md border ${getStatusColor(gate.status)}`}
              role="region"
              aria-label={`Status for ${gate.id}`}
            >
              <div className="flex justify-between items-center">
                <h3 className="font-bold text-xl">{gate.id}</h3>
                <span className="font-mono text-sm px-3 py-1 rounded-full bg-black/40">
                  {gate.status}
                </span>
              </div>
              <p className="text-sm opacity-80 mt-2">Density: {gate.density}%</p>

              {gate.status === 'Green' && (
                <div className="mt-4 p-4 bg-white/5 rounded-xl flex items-start gap-4 border border-white/10 shadow-lg" role="alert">
                  <div className="bg-green-500/20 p-2 rounded-lg">
                    <Ticket className="h-5 w-5 flex-shrink-0 text-green-300" aria-hidden="true" />
                  </div>
                  <div>
                    <p className="font-semibold text-green-100">10% Food Discount!</p>
                    <p className="text-xs text-green-300/80 mt-1">Route to this gate and scan your ticket at the nearest food stall.</p>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <h2 className="text-2xl font-semibold flex items-center gap-2 pt-8 border-t border-white/5">
        <Train className="h-6 w-6 text-brandAccent" aria-hidden="true" />
        Live Transport Wait Times
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {data.transport.map((t) => (
          <div key={t.mode} className="glass p-5 rounded-2xl flex items-center justify-between transition-transform duration-300 hover:scale-[1.02] cursor-default group" role="group" aria-label={`${t.mode} wait time`}>
            <span className="font-medium text-gray-400 group-hover:text-gray-300 transition-colors">{t.mode}</span>
            <span className="font-bold text-3xl text-white tracking-tight">{t.wait_time}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

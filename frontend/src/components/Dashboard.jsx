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

      {data.announcement && (
        <div className="bg-gradient-to-r from-red-600 to-orange-500 rounded-xl p-4 text-white shadow-[0_0_20px_rgba(239,68,68,0.4)] flex items-center gap-3 animate-pulse-slow my-4 border border-red-400/50">
          <AlertCircle className="h-6 w-6 flex-shrink-0" aria-hidden="true" />
          <p className="font-bold tracking-wide">{data.announcement}</p>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-400" role="status" aria-live="assertive">
          <AlertCircle className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
          <span className="text-sm">{error}</span>
          <button onClick={() => fetchStatus(true)} className="ml-auto flex items-center gap-1.5 text-xs underline hover:no-underline" aria-label="Retry fetching stadium status">
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" /> Retry
          </button>
        </div>
      )}

      {loading && data.gates.length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-pulse-slow" role="status" aria-live="polite">
          {[1,2,3,4].map(idx => (
            <div key={idx} className="h-[150px] glass rounded-2xl skeleton-bg"></div>
          ))}
        </div>
      ) : (
        <div className="flex flex-col lg:flex-row gap-8 items-start">
          {/* Interactive SVG Stadium Map */}
          <div className="w-full lg:w-1/2 flex justify-center items-center bg-black/20 rounded-2xl border border-white/5 p-8 shadow-inner">
            <svg viewBox="0 0 200 200" className="w-full h-auto max-w-[350px] drop-shadow-2xl">
              {/* Central Pitch */}
              <rect x="70" y="50" width="60" height="100" rx="10" className="fill-green-900/40 stroke-green-500/50 stroke-2" />
              <line x1="70" y1="100" x2="130" y2="100" className="stroke-green-500/50 stroke-1" />
              <circle cx="100" cy="100" r="15" className="fill-transparent stroke-green-500/50 stroke-1" />
              
              {data.gates.map(gate => {
                const getSVGFill = (status) => {
                  if(status === 'Green') return 'fill-green-500/30 stroke-green-400';
                  if(status === 'Yellow') return 'fill-yellow-500/30 stroke-yellow-400';
                  if(status === 'Red') return 'fill-red-500/30 stroke-red-400';
                  return 'fill-gray-500/30 stroke-gray-400';
                };
                const style = `${getSVGFill(gate.status)} stroke-2 transition-colors duration-700`;
                
                if(gate.id.includes('A')) return (
                  <g key={gate.id}>
                    <path d="M 40,30 Q 100,0 160,30 L 140,50 Q 100,25 60,50 Z" className={style} />
                    <text x="100" y="20" textAnchor="middle" fill="white" className="text-[10px] font-bold font-sans">Gate A</text>
                  </g>
                );
                if(gate.id.includes('B')) return (
                  <g key={gate.id}>
                    <path d="M 170,40 Q 200,100 170,160 L 150,140 Q 175,100 150,60 Z" className={style} />
                    <text x="185" y="103" textAnchor="middle" fill="white" className="text-[10px] font-bold font-sans">Gate B</text>
                  </g>
                );
                if(gate.id.includes('C')) return (
                  <g key={gate.id}>
                    <path d="M 40,170 Q 100,200 160,170 L 140,150 Q 100,175 60,150 Z" className={style} />
                    <text x="100" y="190" textAnchor="middle" fill="white" className="text-[10px] font-bold font-sans">Gate C</text>
                  </g>
                );
                if(gate.id.includes('D')) return (
                  <g key={gate.id}>
                    <path d="M 30,40 Q 0,100 30,160 L 50,140 Q 25,100 50,60 Z" className={style} />
                    <text x="15" y="103" textAnchor="middle" fill="white" className="text-[10px] font-bold font-sans">Gate D</text>
                  </g>
                );
                return null;
              })}
            </svg>
          </div>

          {/* Density Cards List */}
          <div className="w-full lg:w-1/2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2 gap-4">
            {data.gates.map((gate) => (
              <div
                key={gate.id}
                className={`p-5 rounded-2xl flex flex-col gap-2 transition-all duration-300 hover:-translate-y-1 hover:brightness-110 backdrop-blur-md border ${getStatusColor(gate.status)}`}
                role="region"
                aria-label={`Status for ${gate.id}`}
              >
                <div className="flex justify-between items-center">
                  <h3 className="font-bold text-lg">{gate.id}</h3>
                  <span className="font-mono text-xs px-2.5 py-1 rounded-full bg-black/40">
                    {gate.status}
                  </span>
                </div>
                <p className="text-xs opacity-80 mt-1">Density: {gate.density}%</p>
  
                {gate.status === 'Green' && (
                  <div className="mt-3 p-3 bg-white/5 rounded-xl flex items-start gap-3 border border-white/10 shadow-lg" role="alert">
                    <div className="bg-green-500/20 p-1.5 rounded-lg shrink-0">
                      <Ticket className="h-4 w-4 text-green-300" aria-hidden="true" />
                    </div>
                    <div>
                      <p className="font-semibold text-green-100 text-[13px]">10% Food Discount!</p>
                      <p className="text-[11px] text-green-300/80 mt-0.5 leading-tight">Route here to claim at nearest stall.</p>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
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

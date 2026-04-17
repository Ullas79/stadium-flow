import React, { useState, useEffect } from 'react';
import { Map, Train, Ticket } from 'lucide-react';

/**
 * Dashboard Component
 * Polls the backend for stadium gate status and transport wait times.
 */
export default function Dashboard() {
  const [data, setData] = useState({ gates: [], transport: [] });
  const [loading, setLoading] = useState(true);

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/stadium/status');
      if (res.ok) {
        const json = await res.json();
        setData(json.data);
      }
    } catch (err) {
      console.error("Failed to fetch stadium status", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000); // Poll every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status) => {
    switch(status) {
      case 'Green': return 'bg-green-500/10 text-green-400 border-green-500/30';
      case 'Yellow': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30';
      case 'Red': return 'bg-red-500/10 text-red-400 border-red-500/30';
      default: return 'bg-gray-500/10 text-gray-400 border-gray-500/30';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold flex items-center gap-2">
          <Map className="h-6 w-6 text-brandAccent" aria-hidden="true" />
          Gate Density Monitor
        </h2>
      </div>

      {loading ? (
        <div className="h-32 flex items-center justify-center text-gray-400" aria-live="polite">
          Loading stadium data...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data.gates.map((gate) => (
            <div 
              key={gate.id} 
              className={`p-6 rounded-2xl border flex flex-col gap-2 transition-all ${getStatusColor(gate.status)}`}
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
                <div className="mt-4 p-4 bg-black/30 rounded-xl flex items-start gap-3 border border-white/5" role="alert">
                  <Ticket className="h-5 w-5 flex-shrink-0 text-white mt-1" aria-hidden="true" />
                  <div>
                    <p className="font-semibold text-white">10% Food Discount!</p>
                    <p className="text-xs text-green-200 mt-1">Route to this gate and scan your ticket at the nearest food stall.</p>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <h2 className="text-2xl font-semibold flex items-center gap-2 pt-8 border-t border-gray-800">
        <Train className="h-6 w-6 text-brandAccent" aria-hidden="true" />
        Live Transport Wait Times
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {data.transport?.map((t, idx) => (
          <div key={idx} className="bg-darkCard border border-gray-800 p-5 rounded-2xl flex items-center justify-between" role="group" aria-label={`${t.mode} wait time`}>
            <span className="font-medium text-gray-400">{t.mode}</span>
            <span className="font-bold text-2xl text-white">{t.wait_time}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

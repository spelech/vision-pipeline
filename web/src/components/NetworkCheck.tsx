import { useState, useEffect } from 'react';
import { WifiOff } from 'lucide-react';

export function NetworkCheck() {
  const [isOnline, setIsOnline] = useState(typeof navigator !== 'undefined' ? navigator.onLine : true);

  useEffect(() => {
    // Simple connection check to backend when app loads
    fetch('/api/config')
      .then(res => {
        if (!res.ok) {
          console.error("Connection check failed with status:", res.status);
        } else {
          console.log("Connection check successful");
        }
      })
      .catch(err => {
         console.error("Connection check failed completely:", err);
      });

    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  if (isOnline) return null;

  return (
    <div className="fixed top-20 left-0 w-full z-[80] pointer-events-none flex justify-center px-4">
      <div className="glass-dark px-4 py-2.5 rounded-full border border-orange-500/25 bg-black/60 shadow-lg shadow-black/40 flex items-center gap-2 pointer-events-auto">
        <WifiOff className="w-4 h-4 text-orange-400 animate-pulse" />
        <span className="text-[10px] font-black uppercase tracking-wider text-orange-400 animate-pulse">Offline Mode</span>
        <span className="text-[10px] text-white/50 font-medium">Captures will queue locally</span>
      </div>
    </div>
  );
}

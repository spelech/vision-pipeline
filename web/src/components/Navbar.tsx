import { useState } from 'react';
import { Camera, Menu, X } from 'lucide-react';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export function Navbar({ activeTab, setActiveTab }: NavbarProps) {
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const tabs = ['identify', 'batch', 'review', 'pipelines', 'system'];

  const handleTabClick = (tab: string) => {
    setActiveTab(tab);
    setIsMobileOpen(false);
  };

  return (
    <nav className="fixed top-0 w-full z-50 glass-dark border-b border-white/5 px-6 py-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-gradient-to-tr from-blue-600 to-purple-500 rounded-xl shadow-lg shadow-blue-500/20 flex items-center justify-center">
            <Camera className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-lg font-black tracking-tighter uppercase italic flex items-center gap-2">
            <div>Vision<span className="text-blue-500 ml-1">Pipeline</span></div>
            <span className="px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-[8px] tracking-[0.2em] font-black text-white/30 not-italic">V3.4.0</span>
          </h1>
        </div>

        <button
          type="button"
          aria-label={isMobileOpen ? 'Close menu' : 'Open menu'}
          className="p-3 rounded-xl border border-white/15 text-white/80 hover:text-white hover:border-white/30 transition-colors shrink-0"
          onClick={() => setIsMobileOpen((prev) => !prev)}
        >
          {isMobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {isMobileOpen && (
        <div className="mt-3 border-t border-white/10 pt-3">
          <div className="max-w-7xl mx-auto px-1">
            <div className="glass rounded-2xl p-2 border border-white/10 space-y-1">
              {tabs.map(tab => (
                <button
                  key={tab}
                  onClick={() => handleTabClick(tab)}
                  className={`w-full px-4 py-3 rounded-xl text-left text-[11px] font-black uppercase tracking-widest transition-all ${
                    activeTab === tab ? 'bg-white text-black' : 'text-white/70 hover:text-white hover:bg-white/5'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}

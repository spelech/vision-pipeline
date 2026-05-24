import React, { useState, useEffect } from 'react';
import { 
  Camera, 
  Box, 
  CheckCircle2, 
  Trash2, 
  ChevronDown
} from 'lucide-react';

interface Asset {
  id: string;
  filename: string;
  original_filename: string;
  brand?: string;
  category?: string;
  description?: string;
  product_type: 'product' | 'food';
  edit_data: any;
  selected_services: string[];
}

export default function App() {
  const [queue, setQueue] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('identify');

  useEffect(() => {
    fetchQueue();
  }, []);

  const fetchQueue = async () => {
    try {
      setLoading(true);
      const resp = await fetch('/api/queue');
      const data = await resp.json();
      setQueue(data);
    } catch (e) {
      console.error('Failed to fetch queue', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white selection:bg-blue-500/30">
      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 glass-dark border-b border-white/5 px-6 py-4">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-gradient-to-tr from-blue-600 to-purple-500 rounded-xl shadow-lg shadow-blue-500/20 flex items-center justify-center">
              <Camera className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-lg font-black tracking-tighter uppercase italic">Vision<span className="text-blue-500 ml-1">Pipeline</span></h1>
          </div>
          
          <div className="flex bg-white/5 p-1 rounded-2xl border border-white/5">
            {['identify', 'review', 'system'].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-6 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                  activeTab === tab ? 'bg-white text-black' : 'text-white/40 hover:text-white'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto pt-32 px-6 pb-20">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
          
          {/* Main Workspace */}
          <div className="lg:col-span-8 space-y-8">
            <header className="flex justify-between items-end">
              <div>
                <h2 className="text-4xl font-extrabold tracking-tight mb-2">Ingestion Queue</h2>
                <p className="text-white/40 font-medium">Review and process assets identified by the vision pipeline.</p>
              </div>
              <button 
                onClick={fetchQueue}
                className="bg-white/5 hover:bg-white/10 px-4 py-2 rounded-xl text-[10px] font-bold uppercase tracking-widest"
              >
                Refresh
              </button>
            </header>

            <div className="space-y-4">
              {loading ? (
                <div className="py-20 flex justify-center">
                  <div className="w-8 h-8 border-2 border-white/10 border-t-white rounded-full animate-spin" />
                </div>
              ) : queue.length === 0 ? (
                <div className="glass rounded-[3rem] p-20 flex flex-center text-center">
                  <div className="max-w-xs mx-auto space-y-4">
                    <Box className="w-12 h-12 text-white/5 mx-auto" />
                    <p className="text-sm text-white/20 font-bold uppercase tracking-widest">Waiting for assets...</p>
                  </div>
                </div>
              ) : (
                queue.map((item) => (
                  <AssetItem key={item.id} item={item} />
                ))
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-4 space-y-6">
             <div className="glass rounded-[2rem] p-8 space-y-6 sticky top-32">
                <h3 className="label-apple">Pipeline Stats</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-white/5 rounded-2xl p-4">
                    <div className="text-2xl font-black">{queue.length}</div>
                    <div className="text-[9px] uppercase tracking-widest text-white/30">Pending</div>
                  </div>
                  <div className="bg-white/5 rounded-2xl p-4">
                    <div className="text-2xl font-black text-green-500">?</div>
                    <div className="text-[9px] uppercase tracking-widest text-white/30">Processed</div>
                  </div>
                </div>
             </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function AssetItem({ item }: { item: Asset }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="glass rounded-[2rem] overflow-hidden transition-all hover:border-white/20">
      <div className="p-6 flex items-center gap-6">
        <div className="w-24 h-24 rounded-2xl overflow-hidden glass shrink-0 relative group">
          <img 
            src={`/data/uploads/${item.filename}`} 
            className="w-full h-full object-cover"
            alt={item.original_filename}
          />
        </div>
        
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-tighter ${
              item.product_type === 'food' ? 'bg-orange-500 text-white' : 'bg-blue-500 text-white'
            }`}>
              {item.product_type}
            </span>
            <span className="text-[9px] font-mono text-white/20">{item.id.split('-')[0]}</span>
          </div>
          <h3 className="text-xl font-bold tracking-tight">{item.edit_data.product_name || 'Unidentified Asset'}</h3>
          <p className="text-white/40 text-xs truncate max-w-sm">{item.edit_data.description || 'No description provided'}</p>
        </div>

        <button 
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-12 h-12 rounded-full glass flex items-center justify-center hover:bg-white/10 transition-all active:scale-90"
        >
          <ChevronDown className={`w-5 h-5 transition-transform duration-500 ${isExpanded ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {isExpanded && (
        <div className="p-8 border-t border-white/5 bg-white/[0.01] space-y-8 animate-in slide-in-from-top-4 duration-300">
           <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="space-y-1">
                <label className="label-apple">Brand</label>
                <input 
                  className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-sm focus:outline-none focus:border-blue-500/50" 
                  defaultValue={item.edit_data.brand}
                />
              </div>
              <div className="space-y-1">
                <label className="label-apple">Category</label>
                <input 
                  className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-sm focus:outline-none focus:border-blue-500/50" 
                  defaultValue={item.edit_data.category}
                />
              </div>
              <div className="space-y-1">
                <label className="label-apple">Location</label>
                <input 
                  className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-sm focus:outline-none focus:border-blue-500/50" 
                  defaultValue={item.edit_data.location}
                />
              </div>
              <div className="md:col-span-2 lg:col-span-3 space-y-1">
                <label className="label-apple">Description</label>
                <textarea 
                  className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-sm focus:outline-none focus:border-blue-500/50 h-24"
                  defaultValue={item.edit_data.description}
                />
              </div>
           </div>

           <div className="flex gap-4">
              <button className="flex-1 py-4 rounded-2xl text-[10px] font-black uppercase tracking-widest text-red-500/60 hover:bg-red-500/5 transition-all">
                Discard Asset
              </button>
              <button className="flex-[2] btn-apple py-4 text-[10px] font-black uppercase tracking-[0.3em] shadow-xl shadow-white/5">
                Execute & Sync
              </button>
           </div>
        </div>
      )}
    </div>
  );
}

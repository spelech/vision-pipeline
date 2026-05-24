import React, { useState, useEffect } from 'react';
import { 
  Camera, Box, ChevronDown, CheckCircle2, AlertCircle, Edit3, Send, Trash2, X, Search
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
  const [activeTab, setActiveTab] = useState('review');
  const [previewItem, setPreviewItem] = useState<{item: Asset, service: string, payload: any} | null>(null);

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

  const handlePreview = async (item: Asset) => {
    const service = item.selected_services[0] || 'homebox';
    try {
      const resp = await fetch(`/api/preview/${service}?item_id=${item.id}`);
      const data = await resp.json();
      setPreviewItem({ item, service, payload: data.payload });
    } catch (e) {
      console.error('Preview failed', e);
    }
  };

  const executeItem = async (item: Asset, overrides?: any) => {
    try {
      const resp = await fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: item.id,
          service_names: item.selected_services,
          overrides: overrides || item.edit_data
        })
      });
      if (resp.ok) {
        setQueue(q => q.filter(i => i.id !== item.id));
        setPreviewItem(null);
      }
    } catch (e) {
      console.error('Execution failed', e);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white selection:bg-blue-500/30 font-sans">
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
          <div className="lg:col-span-8 space-y-8">
            <header className="flex justify-between items-end">
              <div>
                <h2 className="text-4xl font-extrabold tracking-tight mb-2">Review Queue</h2>
                <p className="text-white/40 font-medium italic">Vibe-coding the future of asset ingestion.</p>
              </div>
              <button onClick={fetchQueue} className="bg-white/5 hover:bg-white/10 px-4 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase">Sync DB</button>
            </header>

            <div className="space-y-4">
              {loading ? (
                <div className="py-20 flex justify-center"><div className="w-8 h-8 border-2 border-white/10 border-t-white rounded-full animate-spin" /></div>
              ) : queue.map(item => (
                <AssetCard key={item.id} item={item} onPreview={() => handlePreview(item)} onExecute={(overrides) => executeItem(item, overrides)} />
              ))}
            </div>
          </div>

          <aside className="lg:col-span-4">
            <div className="glass rounded-[2rem] p-8 space-y-6 sticky top-32">
              <h3 className="label-apple">Status Dashboard</h3>
              <div className="grid grid-cols-2 gap-4">
                <StatusStat label="Queue" value={queue.length} color="text-white" />
                <StatusStat label="Active" value={0} color="text-blue-500" />
              </div>
            </div>
          </aside>
        </div>
      </main>

      {previewItem && (
        <PreviewModal 
          preview={previewItem} 
          onClose={() => setPreviewItem(null)} 
          onConfirm={(overrides) => executeItem(previewItem.item, overrides)}
        />
      )}
    </div>
  );
}

function StatusStat({ label, value, color }: { label: string, value: number, color: string }) {
  return (
    <div className="bg-white/5 rounded-2xl p-4">
      <div className={`text-2xl font-black ${color}`}>{value}</div>
      <div className="text-[9px] uppercase tracking-widest text-white/30">{label}</div>
    </div>
  );
}

function AssetCard({ item, onPreview, onExecute }: { item: Asset, onPreview: () => void, onExecute: (overrides: any) => void }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [editData, setEditData] = useState(item.edit_data);

  return (
    <div className="glass rounded-[2rem] overflow-hidden transition-all hover:border-white/20">
      <div className="p-6 flex items-center gap-6">
        <div className="w-24 h-24 rounded-2xl overflow-hidden bg-white/5 shrink-0">
          <img src={`/data/uploads/${item.filename}`} className="w-full h-full object-cover" alt="" />
        </div>
        <div className="flex-1">
          <div className="flex gap-2 mb-1">
            <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase ${item.product_type === 'food' ? 'bg-orange-500' : 'bg-blue-500'}`}>{item.product_type}</span>
          </div>
          <h3 className="text-xl font-bold">{editData.product_name || 'New Asset'}</h3>
          <p className="text-white/40 text-xs truncate max-w-sm">{item.filename}</p>
        </div>
        <button onClick={() => setIsExpanded(!isExpanded)} className="w-12 h-12 rounded-full glass flex items-center justify-center hover:bg-white/10">
          <ChevronDown className={`w-5 h-5 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {isExpanded && (
        <div className="p-8 border-t border-white/5 bg-white/[0.01] space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Field label="Brand" value={editData.brand} onChange={(v) => setEditData({...editData, brand: v})} />
            <Field label="Category" value={editData.category} onChange={(v) => setEditData({...editData, category: v})} />
            <div className="md:col-span-2">
              <label className="label-apple">Description</label>
              <textarea 
                className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-sm h-24 focus:outline-none"
                value={editData.description}
                onChange={(e) => setEditData({...editData, description: e.target.value})}
              />
            </div>
          </div>
          <div className="flex gap-4">
            <button onClick={onPreview} className="flex-1 py-4 glass rounded-2xl text-[10px] font-black uppercase tracking-widest flex items-center justify-center gap-2">
              <Search className="w-3 h-3" /> Preview JSON
            </button>
            <button onClick={() => onExecute(editData)} className="flex-[2] btn-apple py-4 text-[10px] font-black uppercase tracking-widest flex items-center justify-center gap-2">
              <Send className="w-3 h-3" /> Execute & Sync
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, value, onChange }: { label: string, value: string, onChange: (v: string) => void }) {
  return (
    <div className="space-y-1">
      <label className="label-apple">{label}</label>
      <input className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-sm focus:outline-none" value={value || ''} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function PreviewModal({ preview, onClose, onConfirm }: { preview: {item: Asset, service: string, payload: any}, onClose: () => void, onConfirm: (overrides: any) => void }) {
  const [editedPayload, setEditedPayload] = useState(JSON.stringify(preview.payload, null, 2));

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-black/80 backdrop-blur-md">
      <div className="glass-dark w-full max-w-4xl max-h-[90vh] rounded-[3rem] flex flex-col overflow-hidden shadow-2xl border border-white/10">
        <div className="p-8 border-b border-white/5 flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-black">Pre-flight Review</h2>
            <p className="text-[10px] text-white/40 uppercase tracking-widest font-black">Destination: <span className="text-blue-500">{preview.service}</span></p>
          </div>
          <button onClick={onClose} className="w-10 h-10 rounded-full glass flex items-center justify-center hover:bg-white/20 transition-all"><X className="w-5 h-5" /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-8 space-y-4">
          <label className="label-apple">Transmission Payload</label>
          <textarea 
            className="w-full h-full min-h-[400px] bg-black/50 rounded-2xl p-6 font-mono text-sm text-blue-300 border border-white/5 focus:outline-none focus:border-blue-500/30"
            value={editedPayload}
            onChange={(e) => setEditedPayload(e.target.value)}
          />
        </div>
        <div className="p-8 border-t border-white/5 flex gap-4">
          <button onClick={onClose} className="flex-1 py-4 glass rounded-2xl text-[10px] font-black uppercase tracking-widest">Cancel</button>
          <button onClick={() => onConfirm(JSON.parse(editedPayload))} className="flex-[2] btn-apple py-4 text-[10px] font-black uppercase tracking-widest">Confirm & Push Assets</button>
        </div>
      </div>
    </div>
  );
}

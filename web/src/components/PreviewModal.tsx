import { useState } from 'react';
import { X, Save, AlertCircle } from 'lucide-react';
import type { Asset } from '../types';

interface PreviewModalProps {
  preview: {
    item: Asset;
    service: string;
    payload: Record<string, unknown>;
  };
  onClose: () => void;
  onConfirm: (overrides: Record<string, unknown>) => void;
}

export function PreviewModal({ preview, onClose, onConfirm }: PreviewModalProps) {
  const [editedPayload, setEditedPayload] = useState(JSON.stringify(preview.payload, null, 2));
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = () => {
    try {
      const parsed = JSON.parse(editedPayload);
      onConfirm(parsed);
    } catch {
      setError("Invalid JSON format. Please check your syntax.");
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 bg-black/90 backdrop-blur-xl">
      <div className="glass-dark w-full max-w-6xl max-h-[95vh] rounded-[2.5rem] flex flex-col overflow-hidden shadow-2xl border border-white/10">
        <div className="p-6 border-b border-white/5 flex justify-between items-center bg-white/[0.02]">
          <div>
            <h2 className="text-xl font-black flex items-center gap-2">
              Pre-flight Review
              <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 text-[8px] uppercase tracking-[0.2em]">Transmission Ready</span>
            </h2>
            <p className="text-[9px] text-white/30 uppercase tracking-widest font-black mt-1">Destination: <span className="text-white">{preview.service}</span></p>
          </div>
          <button onClick={onClose} className="w-10 h-10 rounded-full glass flex items-center justify-center hover:bg-white/10 transition-all">
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto flex flex-col lg:flex-row divide-y lg:divide-y-0 lg:divide-x divide-white/5">
          {/* Image Sidebar */}
          <div className="lg:w-1/3 p-8 space-y-6 flex flex-col">
            <h3 className="label-apple">Reference Image</h3>
            <div className="flex-1 rounded-2xl overflow-hidden bg-black/40 border border-white/5 relative group min-h-[200px]">
              <img 
                src={`/uploads/${preview.item.image_path}`} 
                className="w-full h-full object-contain" 
                alt="Asset" 
              />
              <div className="absolute inset-0 bg-blue-500/10 opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <div className="p-4 bg-white/5 rounded-xl border border-white/5">
              <p className="text-[10px] font-bold text-white/40 uppercase mb-2">Metadata</p>
              <div className="space-y-1 text-[11px]">
                 <div className="flex justify-between"><span className="text-white/30">ID</span> <span>{preview.item.id}</span></div>
                 <div className="flex justify-between"><span className="text-white/30">Type</span> <span className="capitalize">{preview.item.product_type}</span></div>
                 <div className="flex justify-between"><span className="text-white/30">Status</span> <span className="text-orange-400">{preview.item.status}</span></div>
              </div>
            </div>
          </div>

          {/* Code Editor */}
          <div className="lg:w-2/3 p-8 flex flex-col space-y-4">
            <div className="flex justify-between items-center">
              <label className="label-apple">API Payload (JSON)</label>
              {error && <span className="text-red-400 text-[10px] font-bold flex items-center gap-1"><AlertCircle className="w-3 h-3" /> {error}</span>}
            </div>
            <textarea 
              className="flex-1 w-full min-h-[300px] bg-black/60 rounded-2xl p-6 font-mono text-[13px] leading-relaxed text-blue-300 border border-white/5 focus:outline-none focus:border-blue-500/30 selection:bg-blue-500/30 outline-none transition-all"
              value={editedPayload}
              onChange={(e) => {
                setEditedPayload(e.target.value);
                setError(null);
              }}
              spellCheck={false}
            />
          </div>
        </div>

        <div className="p-8 border-t border-white/5 flex flex-col sm:flex-row gap-4 bg-white/[0.01]">
          <button onClick={onClose} className="flex-1 py-4 glass rounded-[1.5rem] text-[10px] font-black uppercase tracking-widest hover:bg-white/10 transition-all">Cancel</button>
          <button onClick={handleConfirm} className="flex-[2] btn-apple py-4 text-[10px] font-black uppercase tracking-widest flex items-center justify-center gap-2 group">
            <Save className="w-4 h-4 group-hover:scale-110 transition-transform" /> Confirm & Transmit to {preview.service}
          </button>
        </div>
      </div>
    </div>
  );
}

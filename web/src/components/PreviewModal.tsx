import React, { useState } from 'react';
import { X } from 'lucide-react';
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

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-black/80 backdrop-blur-md">
      <div className="glass-dark w-full max-w-4xl max-h-[90vh] rounded-[3rem] flex flex-col overflow-hidden shadow-2xl border border-white/10">
        <div className="p-8 border-b border-white/5 flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-black">Pre-flight Review</h2>
            <p className="text-[10px] text-white/40 uppercase tracking-widest font-black">Destination: <span className="text-blue-500">{preview.service}</span></p>
          </div>
          <button onClick={onClose} className="w-10 h-10 rounded-full glass flex items-center justify-center hover:bg-white/20 transition-all">
            <X className="w-5 h-5" />
          </button>
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

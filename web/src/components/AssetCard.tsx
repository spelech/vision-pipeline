import { useState } from 'react';
import { ChevronDown, Search, Send } from 'lucide-react';
import type { Asset } from '../types';
import { Field } from './Field';

interface AssetCardProps {
  item: Asset;
  isSelected?: boolean;
  onToggleSelect?: () => void;
  onPreview: () => void;
  onExecute: (overrides: Record<string, unknown>) => void;
}

export function AssetCard({ item, isSelected, onToggleSelect, onPreview, onExecute }: AssetCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [editData, setEditData] = useState(item.edit_data || {});

  return (
    <div className={`glass rounded-[2rem] overflow-hidden transition-all ${isSelected ? 'border-blue-500 shadow-[0_0_20px_rgba(59,130,246,0.3)]' : 'hover:border-white/20'}`}>
      <div className="p-6 flex items-center gap-6">
        {onToggleSelect && (
          <div onClick={onToggleSelect} className="cursor-pointer px-2">
            <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors ${isSelected ? 'bg-blue-500 border-blue-500' : 'border-white/30'}`}>
              {isSelected && <div className="w-2.5 h-2.5 bg-white rounded-full" />}
            </div>
          </div>
        )}
        <div className="w-24 h-24 rounded-2xl overflow-hidden bg-white/5 shrink-0">
          <img src={`/data/uploads/${item.filename}`} className="w-full h-full object-cover" alt="" />
        </div>
        <div className="flex-1">
          <div className="flex gap-2 mb-1">
            <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase ${item.product_type === 'food' ? 'bg-orange-500' : 'bg-blue-500'}`}>{item.product_type}</span>
          </div>
          <h3 className="text-xl font-bold">{editData?.product_name || 'New Asset'}</h3>
          <p className="text-white/40 text-[10px] font-medium tracking-tight truncate max-w-sm">{item.filename}</p>
        </div>
        <button 
          onClick={() => setIsExpanded(!isExpanded)} 
          className="w-12 h-12 rounded-full glass flex items-center justify-center hover:bg-white/10"
          aria-label="Expand Asset"
        >
          <ChevronDown className={`w-5 h-5 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {isExpanded && (
        <div className="p-8 border-t border-white/5 bg-white/[0.01] space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Field label="Brand" value={editData.brand || ""} onChange={(v) => setEditData({...editData, brand: v})} />
            <Field label="Category" value={editData.category || ""} onChange={(v) => setEditData({...editData, category: v})} />
            <div className="md:col-span-2">
              <label htmlFor="description" className="label-apple">Description</label>
              <textarea 
                id="description"
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

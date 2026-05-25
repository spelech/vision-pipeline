import { useState } from 'react';
import { ChevronDown, Search, Send, Box, Utensils, Eye, DollarSign, Info } from 'lucide-react';
import type { Asset, AssetEditData } from '../types';
import { Field } from './Field';

interface AssetCardProps {
  item: Asset;
  isSelected?: boolean;
  onToggleSelect?: () => void;
  onPreview: (service: string, overrides: Record<string, unknown>) => void;
  onExecute: (services: string[], overrides: Record<string, unknown>) => void;
}

export function AssetCard({ item, isSelected, onToggleSelect, onPreview, onExecute }: AssetCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [editData, setEditData] = useState<AssetEditData>(
    (item.user_overrides && Object.keys(item.user_overrides).length > 0) 
      ? (item.user_overrides as AssetEditData) 
      : ((item.ai_output?.llm_output as AssetEditData) || {})
  );
  const [selectedServices, setSelectedServices] = useState<string[]>(
    item.selected_services?.length ? item.selected_services : [item.product_type === 'food' ? 'mealie' : 'homebox']
  );
  const [showTechnical, setShowTechnical] = useState(false);

  const toggleService = (svc: string) => {
    setSelectedServices(prev => 
      prev.includes(svc) ? prev.filter(s => s !== svc) : [...prev, svc]
    );
  };

  const services = [
    { id: 'homebox', name: 'Homebox', icon: Box, color: 'text-blue-400' },
    { id: 'mealie', name: 'Mealie', icon: Utensils, color: 'text-orange-400' },
    { id: 'changedetection', name: 'CD.io', icon: Eye, color: 'text-purple-400' },
    { id: 'pricebuddy', name: 'Price', icon: DollarSign, color: 'text-green-400' },
  ];

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
        <div 
          className="w-24 h-24 rounded-2xl overflow-hidden bg-white/5 shrink-0 cursor-pointer hover:scale-105 transition-transform"
          onClick={() => window.open(`/uploads/${item.image_path}`, '_blank')}
        >
          <img src={`/uploads/${item.image_path}`} className="w-full h-full object-contain bg-black/40" alt="" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex gap-2 mb-1 overflow-x-auto no-scrollbar">
            <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase shrink-0 ${item.product_type === 'food' ? 'bg-orange-500' : 'bg-blue-500'}`}>{item.product_type}</span>
            {selectedServices.map(s => (
              <span key={s} className="px-2 py-0.5 rounded text-[8px] font-black uppercase bg-white/10 text-white/70 shrink-0">{s}</span>
            ))}
          </div>
          <h3 className="text-xl font-bold truncate">{editData?.product_name || 'New Asset'}</h3>
          <p className="text-white/40 text-[10px] font-medium tracking-tight truncate">{item.image_path}</p>
        </div>
        <button 
          onClick={() => setIsExpanded(!isExpanded)} 
          className="w-12 h-12 rounded-full glass flex items-center justify-center hover:bg-white/10 shrink-0"
          aria-label="Expand Asset"
        >
          <ChevronDown className={`w-5 h-5 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {isExpanded && (
        <div className="p-8 border-t border-white/5 bg-white/[0.01] space-y-8">
          {/* Service Selection */}
          <div className="space-y-4">
            <h4 className="label-apple">Destination Services</h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {services.map(svc => {
                const Icon = svc.icon;
                const active = selectedServices.includes(svc.id);
                return (
                  <button
                    key={svc.id}
                    onClick={() => toggleService(svc.id)}
                    className={`p-3 rounded-2xl border transition-all flex flex-col items-center gap-2 ${active ? 'bg-white/10 border-blue-500/50 shadow-lg shadow-blue-500/10' : 'bg-white/5 border-white/5 opacity-40 hover:opacity-100'}`}
                  >
                    <Icon className={`w-5 h-5 ${active ? svc.color : 'text-white'}`} />
                    <span className="text-[9px] font-black uppercase tracking-wider">{svc.name}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Field label="Product Name" value={editData.product_name || ""} onChange={(v) => setEditData({...editData, product_name: v})} />
            <Field label="Brand" value={editData.brand || ""} onChange={(v) => setEditData({...editData, brand: v})} />
            <Field label="Category" value={editData.category || ""} onChange={(v) => setEditData({...editData, category: v})} />
            <Field label="Price Hint" value={editData.price || ""} onChange={(v) => setEditData({...editData, price: v})} />
            <div className="md:col-span-2">
              <label htmlFor="description" className="label-apple">Description</label>
              <textarea 
                id="description"
                className="w-full bg-white/5 border border-white/10 rounded-xl p-4 text-sm h-32 focus:outline-none focus:border-blue-500/30 transition-colors"
                value={editData.description || ""}
                onChange={(e) => setEditData({...editData, description: e.target.value})}
              />
            </div>
          </div>

          {/* Technical Info Toggle */}
          <div className="pt-4 border-t border-white/5">
            <button 
              onClick={() => setShowTechnical(!showTechnical)}
              className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-white/30 hover:text-white transition-colors"
            >
              <Info className="w-3 h-3" /> {showTechnical ? 'Hide Technical Data' : 'Show Technical Data'}
            </button>
            {showTechnical && (
              <div className="mt-4 p-6 bg-black/40 rounded-2xl border border-white/5 font-mono text-[10px] text-blue-300/70 overflow-x-auto whitespace-pre">
                {JSON.stringify(item.ai_output, null, 2)}
              </div>
            )}
          </div>

          <div className="flex gap-4 pt-4">
            <button 
              onClick={() => onPreview(selectedServices[0] || 'homebox', editData)} 
              className="flex-1 py-4 glass rounded-2xl text-[10px] font-black uppercase tracking-widest flex items-center justify-center gap-2 disabled:opacity-30"
              disabled={selectedServices.length === 0}
            >
              <Search className="w-3 h-3" /> Preview Payload
            </button>
            <button 
              onClick={() => onExecute(selectedServices, editData)} 
              className="flex-[2] btn-apple py-4 text-[10px] font-black uppercase tracking-widest flex items-center justify-center gap-2 disabled:opacity-30"
              disabled={selectedServices.length === 0}
            >
              <Send className="w-3 h-3" /> Execute & Sync
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

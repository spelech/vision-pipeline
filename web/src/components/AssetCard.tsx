import { useState, useEffect } from 'react';
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

type PipelineStageId = 'barcode' | 'vision' | 'search' | 'refine' | 'sync';

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
  const [logs, setLogs] = useState<string[]>([]);
  const aiSessionId = typeof item.ai_output?.session_id === 'string' ? item.ai_output.session_id : undefined;

  useEffect(() => {
    if (!isExpanded) return;
    
    const sessionId = aiSessionId || `batch-item-${item.id}`;
    
    const fetchLogs = async () => {
      try {
        const resp = await fetch(`/api/logs/${sessionId}`);
        if (resp && resp.ok) {
          const data = await resp.json();
          if (data && Array.isArray(data.logs)) {
            setLogs(data.logs.map((l: { message: string }) => l.message));
          }
        }
      } catch (e) {
        console.error('Failed to fetch logs', e);
      }
    };
    
    void fetchLogs();
  }, [isExpanded, item.id, aiSessionId]);

  const getStageStatus = (stage: PipelineStageId) => {
    const hasLog = (text: string) => logs.some(log => log.includes(text));

    const barcodeStarted = hasLog('[Node: Barcode]');
    const visionStarted = hasLog('[Node: Vision]');
    const searchStarted = hasLog('[Node: Search]');
    const refineStarted = hasLog('[Node: Refine]');
    const syncStarted = hasLog('Checking for existing entries') || hasLog('existing entries');
    const finished = hasLog('🏁') || hasLog('finished') || hasLog('UI updating');

    switch (stage) {
      case 'barcode':
        if (visionStarted || searchStarted || refineStarted || syncStarted || finished) return 'completed';
        if (barcodeStarted) return 'active';
        return 'pending';
      case 'vision':
        if (searchStarted || refineStarted || syncStarted || finished) return 'completed';
        if (visionStarted) return 'active';
        return 'pending';
      case 'search':
        if (refineStarted || syncStarted || finished) return 'completed';
        if (searchStarted) return 'active';
        return 'pending';
      case 'refine':
        if (syncStarted || finished) return 'completed';
        if (refineStarted) return 'active';
        return 'pending';
      case 'sync':
        if (finished) return 'completed';
        if (syncStarted) return 'active';
        return 'pending';
      default:
        return 'pending';
    }
  };

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

          {/* Pipeline Dashboard & Logs */}
          <div className="pt-6 border-t border-white/5 space-y-4">
            <h4 className="label-apple">Pipeline Ingestion History</h4>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Pipeline Stages */}
              <div className="lg:col-span-1 space-y-2">
                <p className="text-[10px] font-bold uppercase tracking-wider text-white/30">Stages</p>
                <div className="space-y-2">
                  {([
                    { id: 'barcode', label: 'Barcode Scanning', icon: '🔍' },
                    { id: 'vision', label: 'Vision Identification', icon: '🤖' },
                    { id: 'search', label: 'Web Enrichment', icon: '🌐' },
                    { id: 'refine', label: 'Data Refinement', icon: '🧠' },
                    { id: 'sync', label: 'Services Sync Check', icon: '🔌' }
                  ] as Array<{ id: PipelineStageId; label: string; icon: string }>).map((stage) => {
                    const status = getStageStatus(stage.id);
                    return (
                      <div
                        key={stage.id}
                        className={`flex items-center gap-3 p-3 rounded-xl border transition-all duration-300 ${
                          status === 'active' ? 'bg-cyan-950/20 border-cyan-500/40 shadow-[0_0_15px_rgba(6,182,212,0.05)]' :
                          status === 'completed' ? 'bg-green-950/10 border-green-500/20' :
                          'bg-white/5 border-white/5 opacity-50'
                        }`}
                      >
                        <span className="text-base shrink-0">{stage.icon}</span>
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] font-bold text-white leading-tight truncate">{stage.label}</p>
                          <p className={`text-[8px] font-black uppercase tracking-wider mt-0.5 ${
                            status === 'active' ? 'text-cyan-400 animate-pulse' :
                            status === 'completed' ? 'text-green-400' :
                            'text-white/30'
                          }`}>
                            {status === 'active' ? 'Processing' : status === 'completed' ? 'Completed' : 'Pending'}
                          </p>
                        </div>
                        <div className="shrink-0">
                          {status === 'active' ? (
                            <div className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                          ) : status === 'completed' ? (
                            <div className="w-2 h-2 rounded-full bg-green-500 flex items-center justify-center text-[6px] text-black font-black">✓</div>
                          ) : (
                            <div className="w-2 h-2 rounded-full bg-white/10" />
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Logs Console */}
              <div className="lg:col-span-2 flex flex-col space-y-2">
                <p className="text-[10px] font-bold uppercase tracking-wider text-white/30">Logs</p>
                <div className="flex-1 bg-black/40 rounded-2xl border border-white/5 p-4 font-mono text-[10px] text-white/70 overflow-y-auto max-h-[190px] space-y-1 scrollbar-thin scrollbar-thumb-white/10 no-scrollbar min-h-[150px]">
                  {logs.length === 0 ? (
                    <p className="text-white/20 italic">No logs available for this session.</p>
                  ) : (
                    logs.map((log, index) => (
                      <div key={index} className="leading-relaxed border-l border-white/5 pl-2">
                        <span className="text-white/30 mr-2">[{index + 1}]</span>
                        <span className={log.includes('❌') || log.includes('⚠️') ? 'text-red-400' : log.includes('✨') || log.includes('🏁') ? 'text-green-400 font-semibold' : 'text-white/80'}>
                          {log}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
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

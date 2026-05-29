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
    const itemImageSrc =
      (typeof item.ai_output?.review_image_data_uri === 'string' && item.ai_output.review_image_data_uri.startsWith('data:image'))
        ? item.ai_output.review_image_data_uri
        : (item.image_path.startsWith('data:image') ? item.image_path : `/uploads/${item.image_path}`);

  type ServiceRunState = 'idle' | 'running' | 'ready' | 'error';

  const asEditableText = (value: unknown, fallback = ''): string => {
    if (value === null || value === undefined || value === '') return fallback;
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return String(value);
    }
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return fallback;
    }
  };

  const [isExpanded, setIsExpanded] = useState(false);
  const [editData, setEditData] = useState<AssetEditData>(
    (item.user_overrides && Object.keys(item.user_overrides).length > 0) 
      ? (item.user_overrides as AssetEditData) 
      : ((item.ai_output?.llm_output as AssetEditData) || {})
  );
  const [selectedServices, setSelectedServices] = useState<string[]>(
    item.selected_services?.length ? item.selected_services : []
  );
  const [expandedServices, setExpandedServices] = useState<Record<string, boolean>>({
    homebox: false,
    mealie: false,
    changedetection: false,
    pricebuddy: false,
  });
  const [serviceRunState, setServiceRunState] = useState<Record<string, ServiceRunState>>({
    homebox: item.selected_services?.includes('homebox') ? 'ready' : 'idle',
    mealie: item.selected_services?.includes('mealie') ? 'ready' : 'idle',
    changedetection: item.selected_services?.includes('changedetection') ? 'ready' : 'idle',
    pricebuddy: item.selected_services?.includes('pricebuddy') ? 'ready' : 'idle',
  });
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
    const hasFailure = (nodeLabel: string) =>
      logs.some(
        (log) =>
          (log.includes('❌') || log.toLowerCase().includes('error')) &&
          log.includes(`[Node: ${nodeLabel}]`)
      );

    const barcodeStarted = hasLog('[Node: Barcode]');
    const visionStarted = hasLog('[Node: Vision]');
    const searchStarted = hasLog('[Node: Search]');
    const refineStarted = hasLog('[Node: Refine]');
    const syncStarted = hasLog('Checking for existing entries') || hasLog('existing entries');
    const finished = hasLog('🏁') || hasLog('finished') || hasLog('UI updating');

    switch (stage) {
      case 'barcode':
        if (hasFailure('Barcode')) return 'failed';
        if (visionStarted || searchStarted || refineStarted || syncStarted || finished) return 'completed';
        if (barcodeStarted) return 'active';
        return 'pending';
      case 'vision':
        if (hasFailure('Vision')) return 'failed';
        if (searchStarted || refineStarted || syncStarted || finished) return 'completed';
        if (visionStarted) return 'active';
        return 'pending';
      case 'search':
        if (hasFailure('Search')) return 'failed';
        if (refineStarted || syncStarted || finished) return 'completed';
        if (searchStarted) return 'active';
        return 'pending';
      case 'refine':
        if (hasFailure('Refine')) return 'failed';
        if (syncStarted || finished) return 'completed';
        if (refineStarted) return 'active';
        return 'pending';
      case 'sync':
        if (logs.some((log) => log.includes('❌') || log.toLowerCase().includes('error'))) return 'failed';
        if (finished) return 'completed';
        if (syncStarted) return 'active';
        return 'pending';
      default:
        return 'pending';
    }
  };

  const generateServiceOutput = async (svc: string) => {
    setServiceRunState((prev) => ({ ...prev, [svc]: 'running' }));
    setExpandedServices((prev) => ({ ...prev, [svc]: false }));
    try {
      const resp = await fetch('/api/service-output/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: Number(item.id), service_name: svc, force: true })
      });
      const data = await resp.json();
      if (resp.ok && data?.success && data?.output?.status === 'ready') {
        const generated = data?.output?.data;
        if (generated && typeof generated === 'object') {
          setEditData((prev) => ({ ...prev, ...(generated as AssetEditData) }));
        }
        setServiceRunState((prev) => ({ ...prev, [svc]: 'ready' }));
        setExpandedServices((prev) => ({ ...prev, [svc]: true }));
        return;
      }
      setServiceRunState((prev) => ({ ...prev, [svc]: 'error' }));
    } catch (error) {
      console.error('Failed to generate service output', error);
      setServiceRunState((prev) => ({ ...prev, [svc]: 'error' }));
    }
  };

  const toggleService = (svc: string) => {
    const isEnabled = selectedServices.includes(svc);
    if (isEnabled) {
      setSelectedServices((prev) => prev.filter((s) => s !== svc));
      setExpandedServices((prev) => ({ ...prev, [svc]: false }));
      setServiceRunState((prev) => ({ ...prev, [svc]: 'idle' }));
      return;
    }

    setSelectedServices((prev) => [...prev, svc]);
    void generateServiceOutput(svc);
  };

  const toggleServiceExpanded = (svc: string) => {
    setExpandedServices((prev) => ({ ...prev, [svc]: !prev[svc] }));
  };

  const services = [
    { id: 'homebox', name: 'Homebox', icon: Box, color: 'text-blue-400' },
    { id: 'mealie', name: 'Mealie', icon: Utensils, color: 'text-orange-400' },
    { id: 'changedetection', name: 'CD.io', icon: Eye, color: 'text-purple-400' },
    { id: 'pricebuddy', name: 'Price', icon: DollarSign, color: 'text-green-400' },
  ];

  const renderServiceFields = (serviceId: string) => {
    if (serviceId === 'homebox') {
      return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Field label="Location" value={asEditableText(editData.location)} onChange={(v) => setEditData({ ...editData, location: v })} />
          <Field label="Quantity" value={String(editData.quantity || '1')} onChange={(v) => setEditData({ ...editData, quantity: v })} />
          <Field label="Purchase Price" value={String(editData.purchase_price || '')} onChange={(v) => setEditData({ ...editData, purchase_price: v })} />
          <Field label="Serial Number" value={String(editData.serial_number || '')} onChange={(v) => setEditData({ ...editData, serial_number: v })} />
          <Field label="Manufacturer" value={String(editData.manufacturer || editData.brand || '')} onChange={(v) => setEditData({ ...editData, manufacturer: v })} />
          <Field label="Model Number" value={String(editData.model_number || '')} onChange={(v) => setEditData({ ...editData, model_number: v })} />
          <div className="md:col-span-2">
            <label htmlFor="homebox-notes" className="label-apple">Homebox Notes</label>
            <textarea
              id="homebox-notes"
              className="w-full bg-white/5 border border-white/10 rounded-xl p-4 text-sm h-28 focus:outline-none focus:border-blue-500/30 transition-colors"
              value={asEditableText(editData.notes)}
              onChange={(e) => setEditData({ ...editData, notes: e.target.value })}
            />
          </div>
          <div className="md:col-span-2">
            <label htmlFor="homebox-tech" className="label-apple">Technical Details</label>
            <textarea
              id="homebox-tech"
              className="w-full bg-white/5 border border-white/10 rounded-xl p-4 text-sm h-24 focus:outline-none focus:border-blue-500/30 transition-colors"
              value={asEditableText(editData.technical_details)}
              onChange={(e) => setEditData({ ...editData, technical_details: e.target.value })}
            />
          </div>
        </div>
      );
    }

    if (serviceId === 'mealie') {
      return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Field label="Yield" value={String(editData.yield || '1 serving')} onChange={(v) => setEditData({ ...editData, yield: v })} />
          <Field label="Prep Time" value={String(editData.prep_time || '')} onChange={(v) => setEditData({ ...editData, prep_time: v })} />
          <Field label="Cook Time" value={String(editData.cook_time || '')} onChange={(v) => setEditData({ ...editData, cook_time: v })} />
          <Field label="Total Time" value={String(editData.total_time || '')} onChange={(v) => setEditData({ ...editData, total_time: v })} />
          <div className="md:col-span-2">
            <label htmlFor="mealie-ingredients" className="label-apple">Ingredients (one per line)</label>
            <textarea
              id="mealie-ingredients"
              className="w-full bg-white/5 border border-white/10 rounded-xl p-4 text-sm h-28 focus:outline-none focus:border-blue-500/30 transition-colors"
              value={String(editData.recipe_ingredients_raw || '')}
              onChange={(e) => setEditData({ ...editData, recipe_ingredients_raw: e.target.value })}
            />
          </div>
          <div className="md:col-span-2">
            <label htmlFor="mealie-instructions" className="label-apple">Instructions (one per line)</label>
            <textarea
              id="mealie-instructions"
              className="w-full bg-white/5 border border-white/10 rounded-xl p-4 text-sm h-28 focus:outline-none focus:border-blue-500/30 transition-colors"
              value={String(editData.recipe_instructions_raw || '')}
              onChange={(e) => setEditData({ ...editData, recipe_instructions_raw: e.target.value })}
            />
          </div>
          <div className="md:col-span-2">
            <label htmlFor="mealie-tags" className="label-apple">Tags (comma separated)</label>
            <input
              id="mealie-tags"
              className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-sm focus:outline-none"
              value={String(editData.tags || '')}
              onChange={(e) => setEditData({ ...editData, tags: e.target.value })}
            />
          </div>
        </div>
      );
    }

    if (serviceId === 'changedetection') {
      return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Field label="Product URL" value={String(editData.product_url || '')} onChange={(v) => setEditData({ ...editData, product_url: v })} />
          <Field label="Tag" value={String(editData.category || 'Vision Pipeline')} onChange={(v) => setEditData({ ...editData, category: v })} />
          <Field label="Check Every (hours)" value={String(editData.check_every_hours || '12')} onChange={(v) => setEditData({ ...editData, check_every_hours: v })} />
          <Field label="Fetch Backend" value={String(editData.fetch_backend || 'html_requests')} onChange={(v) => setEditData({ ...editData, fetch_backend: v })} />
          <div className="md:col-span-2 p-4 rounded-xl border border-white/10 bg-white/5 text-[11px] text-white/60">
            ChangeDetection uses the product URL and title. Add a URL above to generate a meaningful payload preview.
          </div>
        </div>
      );
    }

    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Field label="Barcode" value={String(editData.barcode || '')} onChange={(v) => setEditData({ ...editData, barcode: v })} />
        <Field label="Category Tag" value={String(editData.category || '')} onChange={(v) => setEditData({ ...editData, category: v })} />
        <Field label="Primary URL" value={String(editData.product_url || '')} onChange={(v) => setEditData({ ...editData, product_url: v })} />
        <Field label="Target Price" value={String(editData.target_price || '')} onChange={(v) => setEditData({ ...editData, target_price: v })} />
        <Field label="Currency" value={String(editData.currency || 'USD')} onChange={(v) => setEditData({ ...editData, currency: v })} />
        <Field label="Retailer" value={String(editData.retailer || '')} onChange={(v) => setEditData({ ...editData, retailer: v })} />
        <div className="md:col-span-2 p-4 rounded-xl border border-white/10 bg-white/5 text-[11px] text-white/60">
          Price tracking improves when barcode and shopping URLs are provided.
        </div>
      </div>
    );
  };

  const previewService =
    selectedServices.find((svc) => expandedServices[svc] && serviceRunState[svc] === 'ready') ||
    selectedServices.find((svc) => serviceRunState[svc] === 'ready') ||
    null;

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
          onClick={() => window.open(itemImageSrc, '_blank')}
        >
          <img src={itemImageSrc} className="w-full h-full object-contain bg-black/40" alt="" />
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
            <div className="space-y-3">
              {services.map(svc => {
                const Icon = svc.icon;
                const active = selectedServices.includes(svc.id);
                const expanded = expandedServices[svc.id];
                const runState = serviceRunState[svc.id] ?? 'idle';
                return (
                  <div
                    key={svc.id}
                    className={`rounded-2xl border transition-all ${active ? 'border-blue-500/60 bg-blue-500/10 shadow-[0_0_16px_rgba(59,130,246,0.2)]' : 'border-white/10 bg-white/[0.02]'}`}
                  >
                    <div className="p-4 flex items-center gap-3">
                      <input
                        type="checkbox"
                        aria-label={`Enable ${svc.name}`}
                        checked={active}
                        onChange={() => toggleService(svc.id)}
                        className="h-4 w-4 rounded border-white/30 bg-transparent accent-blue-500"
                      />
                      <Icon className={`w-4 h-4 ${active ? svc.color : 'text-white/60'}`} />
                      <span className="text-[10px] font-black uppercase tracking-widest flex-1">{svc.name}</span>
                      <button
                        onClick={() => toggleServiceExpanded(svc.id)}
                        aria-label={`Expand ${svc.name} details`}
                        className="w-8 h-8 rounded-full border border-white/10 flex items-center justify-center hover:bg-white/5"
                        disabled={!active || runState !== 'ready'}
                      >
                        <ChevronDown className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
                      </button>
                    </div>
                    {active && runState === 'running' && (
                      <div className="px-4 pb-4 border-t border-white/10 pt-4">
                        <p className="text-[10px] uppercase tracking-widest font-black text-cyan-300/90 mb-3">Preparing Service Data...</p>
                        <div className="rounded-xl border border-white/10 bg-white/5 p-4 blur-[2px] pointer-events-none select-none">
                          <div className="h-3 w-1/2 bg-white/20 rounded mb-2" />
                          <div className="h-3 w-3/4 bg-white/10 rounded mb-2" />
                          <div className="h-16 w-full bg-white/10 rounded" />
                        </div>
                      </div>
                    )}
                    {active && runState === 'error' && (
                      <div className="px-4 pb-4 border-t border-white/10 pt-4">
                        <p className="text-[10px] text-red-300/90 uppercase tracking-widest font-black mb-3">
                          Service generation failed.
                        </p>
                        <button
                          onClick={() => {
                            void generateServiceOutput(svc.id);
                          }}
                          className="px-4 py-2 rounded-xl border border-red-400/40 text-red-200 text-[10px] font-black uppercase tracking-widest hover:bg-red-500/10"
                        >
                          Retry Service Run
                        </button>
                      </div>
                    )}
                    {active && runState === 'ready' && expanded && (
                      <div className="px-4 pb-4 border-t border-white/10 pt-4">
                        {renderServiceFields(svc.id)}
                      </div>
                    )}
                  </div>
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
                          status === 'failed' ? 'bg-red-950/20 border-red-500/40 shadow-[0_0_15px_rgba(239,68,68,0.08)]' :
                          status === 'completed' ? 'bg-green-950/10 border-green-500/20' :
                          'bg-white/5 border-white/5 opacity-50'
                        }`}
                      >
                        <span className="text-base shrink-0">{stage.icon}</span>
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] font-bold text-white leading-tight truncate">{stage.label}</p>
                          <p className={`text-[8px] font-black uppercase tracking-wider mt-0.5 ${
                            status === 'active' ? 'text-cyan-400 animate-pulse' :
                            status === 'failed' ? 'text-red-400' :
                            status === 'completed' ? 'text-green-400' :
                            'text-white/30'
                          }`}>
                            {status === 'active' ? 'Processing' : status === 'failed' ? 'Failed' : status === 'completed' ? 'Completed' : 'Pending'}
                          </p>
                        </div>
                        <div className="shrink-0">
                          {status === 'active' ? (
                            <div className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                          ) : status === 'failed' ? (
                            <div className="w-2 h-2 rounded-full bg-red-500" />
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
              onClick={() => {
                if (previewService) {
                  onPreview(previewService, editData);
                }
              }} 
              className="flex-1 py-4 glass rounded-2xl text-[10px] font-black uppercase tracking-widest flex items-center justify-center gap-2 disabled:opacity-30"
              disabled={!previewService}
            >
              <Search className="w-3 h-3" /> Preview Payload
            </button>
            <button 
              onClick={() => onExecute(selectedServices, editData)} 
              className="flex-[2] btn-apple py-4 text-[10px] font-black uppercase tracking-widest flex items-center justify-center gap-2 disabled:opacity-30"
              disabled={selectedServices.length === 0 || selectedServices.some((svc) => serviceRunState[svc] === 'running')}
            >
              <Send className="w-3 h-3" /> Execute & Sync
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

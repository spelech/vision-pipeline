import { useState } from 'react';
import { X, Save, AlertCircle, Edit3, Code } from 'lucide-react';
import type { Asset } from '../types';

interface PreviewFormData {
  name?: string;
  quantity?: number;
  purchasePrice?: number;
  location?: string;
  manufacturer?: string;
  modelNumber?: string;
  serialNumber?: string;
  description?: string;
  notes?: string;
  technical_details?: string;
  recipeIngredients?: unknown[];
  recipeInstructions?: unknown[];
  yield?: string;
  barcode?: string;
  urls?: string[];
  tags?: string[];
  title?: string;
  url?: string;
  tag?: string;
  [key: string]: unknown;
}

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
  const [viewMode, setViewMode] = useState<'form' | 'json'>('form');
  const [formData, setFormData] = useState<PreviewFormData>(preview.payload || {});
  const [editedPayload, setEditedPayload] = useState(JSON.stringify(preview.payload, null, 2));
  const [error, setError] = useState<string | null>(null);

  const imageSrc =
    (typeof preview.item.ai_output?.review_image_data_uri === 'string' && preview.item.ai_output.review_image_data_uri.startsWith('data:image'))
      ? preview.item.ai_output.review_image_data_uri
      : (preview.item.image_path.startsWith('data:image') ? preview.item.image_path : `/uploads/${preview.item.image_path}`);

  const handleViewModeChange = (mode: 'form' | 'json') => {
    if (mode === 'json' && viewMode === 'form') {
      setEditedPayload(JSON.stringify(formData, null, 2));
    } else if (mode === 'form' && viewMode === 'json') {
      try {
        const parsed = JSON.parse(editedPayload);
        setFormData(parsed);
        setError(null);
      } catch {
        setError("Invalid JSON format. Fix the syntax before returning to Form Review.");
        return;
      }
    }
    setViewMode(mode);
  };

  const handleConfirm = () => {
    if (viewMode === 'json') {
      try {
        const parsed = JSON.parse(editedPayload);
        onConfirm(parsed);
      } catch {
        setError("Invalid JSON format. Please check your syntax.");
      }
    } else {
      onConfirm(formData);
    }
  };

  const renderHomeboxForm = () => {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="col-span-2">
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Product Name</label>
          <input
            type="text"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={formData.name || ''}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Quantity</label>
          <input
            type="number"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={formData.quantity !== undefined ? formData.quantity : 1}
            onChange={(e) => setFormData({ ...formData, quantity: parseInt(e.target.value) || 0 })}
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Purchase Price ($)</label>
          <input
            type="number"
            step="0.01"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={formData.purchasePrice !== undefined ? formData.purchasePrice : 0.0}
            onChange={(e) => setFormData({ ...formData, purchasePrice: parseFloat(e.target.value) || 0.0 })}
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Location</label>
          <input
            type="text"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={formData.location || ''}
            onChange={(e) => setFormData({ ...formData, location: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Manufacturer / Brand</label>
          <input
            type="text"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={formData.manufacturer || ''}
            onChange={(e) => setFormData({ ...formData, manufacturer: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Model Number</label>
          <input
            type="text"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={formData.modelNumber || ''}
            onChange={(e) => setFormData({ ...formData, modelNumber: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Serial Number</label>
          <input
            type="text"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={formData.serialNumber || ''}
            onChange={(e) => setFormData({ ...formData, serialNumber: e.target.value })}
          />
        </div>
        <div className="col-span-2">
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Description</label>
          <textarea
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50 min-h-[80px]"
            value={formData.description || ''}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          />
        </div>
        <div className="col-span-2">
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Notes</label>
          <textarea
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50 min-h-[80px]"
            value={formData.notes || ''}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
          />
        </div>
        <div className="col-span-2">
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Technical Details</label>
          <textarea
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50 min-h-[80px]"
            value={formData.technical_details || ''}
            onChange={(e) => setFormData({ ...formData, technical_details: e.target.value })}
          />
        </div>
      </div>
    );
  };

  const renderMealieForm = () => {
    const rawIngredients = Array.isArray(formData.recipeIngredients)
      ? formData.recipeIngredients.map((x) => typeof x === 'object' && x ? ((x as { note?: string }).note || '') : String(x)).join('\n')
      : '';

    const rawInstructions = Array.isArray(formData.recipeInstructions)
      ? formData.recipeInstructions.map((x) => typeof x === 'object' && x ? ((x as { text?: string }).text || '') : String(x)).join('\n')
      : '';

    const handleIngredientsChange = (val: string) => {
      const list = val.split('\n').map(line => ({ note: line }));
      setFormData({ ...formData, recipeIngredients: list });
    };

    const handleInstructionsChange = (val: string) => {
      const list = val.split('\n').map(line => ({ text: line }));
      setFormData({ ...formData, recipeInstructions: list });
    };

    return (
      <div className="grid grid-cols-1 gap-4">
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Recipe Name</label>
          <input
            type="text"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={formData.name || ''}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Yield</label>
          <input
            type="text"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={formData.yield || '1 serving'}
            onChange={(e) => setFormData({ ...formData, yield: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Description</label>
          <textarea
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50 min-h-[80px]"
            value={formData.description || ''}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Ingredients (one per line)</label>
          <textarea
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50 min-h-[120px] font-mono text-xs"
            value={rawIngredients}
            onChange={(e) => handleIngredientsChange(e.target.value)}
            placeholder="e.g.&#10;2 cups of flour&#10;1 tsp of salt"
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Instructions (one step per line)</label>
          <textarea
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50 min-h-[120px] font-mono text-xs"
            value={rawInstructions}
            onChange={(e) => handleInstructionsChange(e.target.value)}
            placeholder="e.g.&#10;Mix flour and salt&#10;Bake at 350F"
          />
        </div>
      </div>
    );
  };

  const renderPriceBuddyForm = () => {
    const rawUrls = Array.isArray(formData.urls) ? formData.urls.join('\n') : '';
    const rawTags = Array.isArray(formData.tags) ? formData.tags.join(', ') : '';

    const handleUrlsChange = (val: string) => {
      const list = val.split('\n').map(x => x.trim()).filter(Boolean);
      setFormData({ ...formData, urls: list });
    };

    const handleTagsChange = (val: string) => {
      const list = val.split(',').map(x => x.trim()).filter(Boolean);
      setFormData({ ...formData, tags: list });
    };

    return (
      <div className="grid grid-cols-1 gap-4">
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Product Name</label>
          <input
            type="text"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={formData.name || ''}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Barcode</label>
          <input
            type="text"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={formData.barcode || ''}
            onChange={(e) => setFormData({ ...formData, barcode: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Tags (comma-separated)</label>
          <input
            type="text"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={rawTags}
            onChange={(e) => handleTagsChange(e.target.value)}
            placeholder="e.g. pantry, milk, grocery"
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">URLs to Track (one per line)</label>
          <textarea
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50 min-h-[120px] font-mono text-xs"
            value={rawUrls}
            onChange={(e) => handleUrlsChange(e.target.value)}
            placeholder="e.g. https://amazon.com/product..."
          />
        </div>
      </div>
    );
  };

  const renderChangeDetectionForm = () => {
    return (
      <div className="grid grid-cols-1 gap-4">
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Title</label>
          <input
            type="text"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={formData.title || ''}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">URL to Monitor</label>
          <input
            type="text"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={formData.url || ''}
            onChange={(e) => setFormData({ ...formData, url: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">Tag</label>
          <input
            type="text"
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            value={formData.tag || ''}
            onChange={(e) => setFormData({ ...formData, tag: e.target.value })}
          />
        </div>
      </div>
    );
  };

  const renderGenericForm = () => {
    return (
      <div className="space-y-4">
        <p className="text-xs text-white/40 italic mb-4">No predefined form view for this service. You can use the Raw JSON editor, or edit these generic fields.</p>
        {Object.keys(formData).map(key => {
          const val = formData[key];
          if (typeof val === 'object' && val !== null) return null;
          return (
            <div key={key}>
              <label className="text-[10px] font-bold text-white/50 tracking-wider uppercase mb-1 block">{key.replace(/_/g, ' ')}</label>
              <input
                type="text"
                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
                value={val !== undefined ? String(val) : ''}
                onChange={(e) => setFormData({ ...formData, [key]: e.target.value })}
              />
            </div>
          );
        })}
      </div>
    );
  };

  const renderFormContent = () => {
    const serviceName = preview.service.toLowerCase();
    switch (serviceName) {
      case 'homebox':
        return renderHomeboxForm();
      case 'mealie':
        return renderMealieForm();
      case 'pricebuddy':
        return renderPriceBuddyForm();
      case 'changedetection':
        return renderChangeDetectionForm();
      default:
        return renderGenericForm();
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
            <div className="flex-1 rounded-2xl overflow-hidden bg-black/40 border border-white/5 relative group min-h-[200px] max-h-[400px]">
              <img 
                src={imageSrc}
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

          {/* Form and JSON Editor */}
          <div className="lg:w-2/3 p-8 flex flex-col space-y-4">
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
              <div className="flex bg-white/5 p-1 rounded-xl self-start">
                <button
                  onClick={() => handleViewModeChange('form')}
                  className={`px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 ${
                    viewMode === 'form' ? 'bg-white text-black shadow' : 'text-white/60 hover:text-white'
                  }`}
                >
                  <Edit3 className="w-3.5 h-3.5" /> Form Review
                </button>
                <button
                  onClick={() => handleViewModeChange('json')}
                  className={`px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 ${
                    viewMode === 'json' ? 'bg-white text-black shadow' : 'text-white/60 hover:text-white'
                  }`}
                >
                  <Code className="w-3.5 h-3.5" /> Raw JSON
                </button>
              </div>

              {error && <span className="text-red-400 text-[10px] font-bold flex items-center gap-1"><AlertCircle className="w-3 h-3" /> {error}</span>}
            </div>

            <div className="flex-1 min-h-[300px]">
              {viewMode === 'json' ? (
                <textarea 
                  className="w-full h-full min-h-[300px] bg-black/60 rounded-2xl p-6 font-mono text-[13px] leading-relaxed text-blue-300 border border-white/5 focus:outline-none focus:border-blue-500/30 selection:bg-blue-500/30 outline-none transition-all"
                  value={editedPayload}
                  onChange={(e) => {
                    setEditedPayload(e.target.value);
                    setError(null);
                  }}
                  spellCheck={false}
                />
              ) : (
                <div className="h-full overflow-y-auto max-h-[50vh] pr-2 space-y-4">
                  {renderFormContent()}
                </div>
              )}
            </div>
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

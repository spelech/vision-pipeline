import { useState, useEffect } from 'react';
import {
  DEFAULT_PIPELINE_MODELS,
  getPipelineNodes,
  isPersistedCustomPipeline,
  getVisionPrompt,
  getRefinePrompt,
  getPromptPreview,
  type Pipeline,
} from './pipelineEditorUtils';

export function PipelineEditor() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [editingPipeline, setEditingPipeline] = useState<Pipeline | null>(null);
  const [editingNode, setEditingNode] = useState<{type: string, index: number} | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const setVisionPrompt = (pipeline: Pipeline, prompt: string): Pipeline => {
    const hasVisionPrompt = pipeline.schema.vision_prompt !== undefined;
    if (hasVisionPrompt) {
      return {
        ...pipeline,
        schema: {
          ...pipeline.schema,
          vision_prompt: { default: prompt }
        }
      };
    }

    return {
      ...pipeline,
      schema: {
        ...pipeline.schema,
        custom_prompt: { default: prompt }
      }
    };
  };

  const fetchPipelines = async () => {
    try {
      const resp = await fetch('/api/pipelines');
      const data = await resp.json();
      if (data.success) {
        setPipelines(data.pipelines);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchConfig = async () => {
    try {
      const [configResult, modelsResult] = await Promise.allSettled([
        fetch('/api/config').then(async (response) => {
          if (!response.ok) {
            throw new Error('Failed to load config');
          }
          return response.json();
        }),
        fetch('/api/models').then(async (response) => {
          if (!response.ok) {
            throw new Error('Failed to load models');
          }
          return response.json();
        })
      ]);

      const configData = configResult.status === 'fulfilled' ? configResult.value : {};
      const modelsData = modelsResult.status === 'fulfilled' ? modelsResult.value : {};

      const favorites = Array.isArray(configData.model_favorites) ? configData.model_favorites : [];
      const catalog = modelsData?.success && Array.isArray(modelsData.models)
        ? modelsData.models.map((m: { id: string }) => m.id)
        : DEFAULT_PIPELINE_MODELS;

      const merged = Array.from(new Set([...favorites, ...catalog]));
      setModels(merged);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchPipelines();
    fetchConfig();
  }, []);

  const createNewPipeline = () => {
    const newPipeline: Pipeline = {
      id: `custom_${Date.now()}`,
      name: "New Custom Sequence",
      schema: {
        active_nodes: { default: ["vision", "refine"] },
        vision_model: { default: models[0] || "qwen/qwen2.5-vl-72b-instruct" },
        vision_prompt: { default: "Analyze the image." },
        refine_prompt: { default: "Refine." },
        scrape_wait_time: { default: 2000 }
      }
    };
    setEditingPipeline(newPipeline);
  };

  const openPipelineEditor = (pipeline: Pipeline) => {
    setEditingPipeline({
      ...pipeline,
      schema: {
        ...pipeline.schema,
        active_nodes: { default: getPipelineNodes(pipeline) }
      }
    });
  };

  const savePipelineChanges = async (saveAsCustomCopy = false) => {
    if (!editingPipeline) return;
    setSaving(true);
    
    // Merge new pipeline into custom_pipelines. 
    // Wait, first we need to fetch all custom_pipelines from config and append/update.
    try {
      const cRes = await fetch('/api/config');
      const cData = await cRes.json();
      const custom = Array.isArray(cData.custom_pipelines) ? cData.custom_pipelines : [];
      const pipelineToSave = saveAsCustomCopy && !isPersistedCustomPipeline(editingPipeline)
        ? {
            ...editingPipeline,
            id: `custom_${Date.now()}`,
            name: `${editingPipeline.name} Copy`
          }
        : editingPipeline;

      const idx = custom.findIndex((p: Pipeline) => p.id === pipelineToSave.id);
      if (idx !== -1) {
        custom[idx] = pipelineToSave;
      } else {
        custom.push(pipelineToSave);
      }

      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ custom_pipelines: custom })
      });
      
      setEditingPipeline(null);
      await fetchPipelines();
    } catch (e) {
      console.error(e);
      alert('Failed to save pipeline');
    } finally {
      setSaving(false);
    }
  };

  const moveNode = (index: number, dir: number) => {
    if (!editingPipeline) return;
    const update = { ...editingPipeline };
    const nodes = [...(update.schema.active_nodes?.default || getPipelineNodes(update))];
    const target = index + dir;
    if (target < 0 || target >= nodes.length) return;
    
    const temp = nodes[index];
    nodes[index] = nodes[target];
    nodes[target] = temp;
    update.schema.active_nodes = { default: nodes };
    setEditingPipeline(update);
  };

  const removeNode = (index: number) => {
    if (!editingPipeline) return;
    const update = { ...editingPipeline };
    const nodes = [...(update.schema.active_nodes?.default || getPipelineNodes(update))];
    nodes.splice(index, 1);
    update.schema.active_nodes = { default: nodes };
    setEditingPipeline(update);
  };

  const addNode = (type: string) => {
    if (!editingPipeline) return;
    const update = { ...editingPipeline };
    const nodes = [...(update.schema.active_nodes?.default || getPipelineNodes(update)), type];
    update.schema.active_nodes = { default: nodes };
    setEditingPipeline(update);
  };

  return (
    <div className="space-y-8 w-full">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-8">
          <div>
              <h2 className="text-[11px] font-black uppercase tracking-[0.5em] text-blue-400">Node Infrastructure</h2>
              <h1 className="text-5xl font-black tracking-tighter">Pipeline Builder</h1>
          </div>
          <div className="flex gap-4">
              <button onClick={fetchPipelines} className="glass-dark px-6 py-4 rounded-xl text-[10px] uppercase font-black tracking-widest text-white/40">Sync Registry</button>
              <button onClick={createNewPipeline} className="btn-apple px-8 py-4 rounded-xl text-[10px] uppercase font-black tracking-widest shadow-2xl">Create Custom</button>
          </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 pb-20">
        {pipelines.map(p => (
          <div key={p.id} className="glass p-6 md:p-10 rounded-[2.5rem] sm:rounded-[3rem] space-y-8 group hover:border-white/20 transition-all border-2 border-white/5 overflow-hidden flex flex-col">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                  <div className="space-y-1">
                      <h3 className="text-2xl sm:text-4xl font-black tracking-tighter text-white">{p.name}</h3>
                      <p className="text-[10px] sm:text-[11px] uppercase text-white/30 tracking-widest font-black">
                        {p.id === 'default' ? 'Core System Sequence' : p.id === 'advanced_playwright' ? 'Advanced Scraping Flow' : isPersistedCustomPipeline(p) ? 'Configurable User Flow' : 'Pipeline Prototype'}
                      </p>
                  </div>
                  <button onClick={() => openPipelineEditor(p)} className="w-full md:w-auto btn-apple px-6 sm:px-10 py-3 sm:py-5 rounded-xl sm:rounded-2xl text-[10px] sm:text-xs font-black uppercase tracking-widest shadow-xl active:scale-95 transition-all">
                    {isPersistedCustomPipeline(p) ? 'Customize Sequence' : 'Inspect Architecture'}
                  </button>
              </div>

              <div className="flex-1 space-y-8">
                <div className="relative py-2 mt-4">
                    <div className="flex flex-wrap items-center gap-y-8 gap-x-2 md:gap-x-4">
                      {getPipelineNodes(p).map((node, index, arr) => (
                          <div key={index} className="flex items-center gap-2 md:gap-4">
                              <div className="glass-dark px-4 md:px-6 py-4 rounded-[1.25rem] border border-white/10 min-w-[110px] md:min-w-[130px] text-center bg-black/40 transition-all hover:bg-white/5">
                                  <span className="text-[9px] block font-black uppercase text-white/20 mb-2 tracking-widest">STAGE {index + 1}</span>
                                  <span className="text-[12px] md:text-[13px] font-black uppercase tracking-[0.2em] text-white/90">{node}</span>
                              </div>
                              {index < arr.length - 1 && (
                                <span className="text-white/10 text-xl font-thin select-none">→</span>
                              )}
                          </div>
                      ))}
                  </div>
              </div>

              <div className="flex flex-wrap gap-3 text-[10px] font-black uppercase tracking-widest text-white/40">
                {p.schema.vision_model?.default && <span className="px-3 py-2 rounded-xl bg-white/5 border border-white/10">Model {p.schema.vision_model.default.split('/')[1] || p.schema.vision_model.default}</span>}
                {(p.schema.custom_prompt?.default !== undefined || p.schema.vision_prompt?.default !== undefined) && (
                  <span className="px-3 py-2 rounded-xl bg-white/5 border border-white/10" title={getVisionPrompt(p)}>
                    Vision prompt: {getPromptPreview(getVisionPrompt(p))}
                  </span>
                )}
                {p.schema.refine_prompt?.default !== undefined && (
                  <span className="px-3 py-2 rounded-xl bg-white/5 border border-white/10" title={getRefinePrompt(p)}>
                    Refine prompt: {getPromptPreview(getRefinePrompt(p))}
                  </span>
                )}
                {p.schema.scrape_wait_time?.default !== undefined && <span className="px-3 py-2 rounded-xl bg-white/5 border border-white/10">Scrape wait {p.schema.scrape_wait_time.default}ms</span>}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Editing Modal */}
      {editingPipeline && (
        <div className="fixed inset-0 z-[1200] bg-black/90 flex items-center justify-center p-4 sm:p-6 backdrop-blur-3xl">
          <div className="glass w-full max-w-4xl rounded-[2.5rem] sm:rounded-[4rem] overflow-hidden flex flex-col max-h-full border-2 border-white/10 shadow-2xl">
              <div className="p-6 sm:p-10 border-b border-white/10 flex justify-between items-center bg-white/[0.02]">
                  <div className="space-y-1">
                      <h2 className="font-black tracking-[0.3em] sm:tracking-[0.5em] uppercase text-[8px] sm:text-[10px] opacity-40">Pipeline Architecture</h2>
                      <h3 className="text-xl sm:text-3xl font-black tracking-tighter text-blue-400">{editingPipeline.name}</h3>
                  </div>
                  <button onClick={() => setEditingPipeline(null)} className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl sm:rounded-2xl glass-dark flex items-center justify-center text-lg sm:text-xl active:scale-90 transition-all">✕</button>
              </div>
              
              <div className="p-6 sm:p-10 overflow-y-auto no-scrollbar space-y-6 sm:space-y-10">
                  <div className="space-y-4">
                      <label className="label-apple ml-2">Label</label>
                      <input 
                        type="text" 
                        value={editingPipeline.name} 
                        onChange={e => setEditingPipeline({...editingPipeline, name: e.target.value})} 
                        className="w-full bg-white/5 border border-white/10 rounded-[1.5rem] sm:rounded-[2rem] p-4 sm:p-6 text-lg sm:text-xl font-black text-white focus:outline-none focus:border-blue-500/50 shadow-inner" 
                      />
                  </div>

                  <div className="space-y-6">
                      <label className="label-apple ml-2">Sequence Configuration (Tap to customize Node)</label>
                      <div className="space-y-3">
                            {editingPipeline.schema.active_nodes?.default.map((node, index, arr) => (
                              <div key={`${node}-${index}`} className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 group">
                                  <div className="flex items-center gap-3 sm:gap-4 flex-1">
                                    <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-[10px] font-black opacity-20 flex-shrink-0">{index + 1}</div>
                                    <button onClick={() => setEditingNode({type: node, index})} className="flex-1 glass p-4 sm:p-5 rounded-2xl flex items-center justify-between border-white/5 hover:border-blue-500/40 transition-all text-left min-w-0">
                                        <div className="flex items-center gap-4 min-w-0">
                                            <span className="text-xl sm:text-2xl flex-shrink-0">{node === 'barcode' ? '🔍' : (node === 'vision' ? '🤖' : (node === 'search' ? '🌐' : (node === 'scrape' ? '🕸️' : '🧠')))}</span>
                                            <div className="min-w-0">
                                              <span className="text-xs sm:text-sm font-black uppercase tracking-widest text-white block">{node}</span>
                                              {node === 'vision' && <span className="text-[10px] text-white/45 truncate block">{getPromptPreview(getVisionPrompt(editingPipeline))}</span>}
                                              {node === 'refine' && <span className="text-[10px] text-white/45 truncate block">{getPromptPreview(getRefinePrompt(editingPipeline))}</span>}
                                            </div>
                                        </div>
                                        <span className="hidden sm:block text-[9px] font-black uppercase text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap ml-4">Configure</span>
                                    </button>
                                  </div>
                                  <div className="flex gap-2 self-end sm:self-auto flex-shrink-0">
                                      <button onClick={() => moveNode(index, -1)} disabled={index === 0} className="w-10 h-10 glass rounded-xl flex items-center justify-center hover:bg-white/10 disabled:opacity-0 transition-all active:scale-95">↑</button>
                                      <button onClick={() => moveNode(index, 1)} disabled={index === arr.length - 1} className="w-10 h-10 glass rounded-xl flex items-center justify-center hover:bg-white/10 disabled:opacity-0 transition-all active:scale-95">↓</button>
                                      <button onClick={() => removeNode(index)} className="w-10 h-10 glass rounded-xl flex items-center justify-center text-red-500/40 hover:text-red-500 transition-colors transition-all active:scale-95">✕</button>
                                  </div>
                              </div>
                          ))}
                      </div>
                      
                      <div className="pt-6 border-t border-white/5 space-y-4">
                          <label className="label-apple ml-2">Available Blocks</label>
                          <div className="flex flex-wrap gap-2">
                              {['barcode', 'vision', 'search', 'scrape', 'refine'].map(type => (
                                  <button 
                                    key={`add-${type}`}
                                    onClick={() => addNode(type)} 
                                    className="px-4 sm:px-6 py-3 rounded-xl bg-white/5 border border-white/10 text-[9px] sm:text-[10px] font-black uppercase tracking-widest hover:bg-white/10 transition-colors active:scale-95"
                                  >
                                    + {type}
                                  </button>
                              ))}
                          </div>
                      </div>
                  </div>
              </div>

              <div className="p-6 sm:p-10 border-t border-white/10 flex flex-col sm:flex-row gap-3 sm:gap-4 bg-black/40">
                  <button onClick={() => setEditingPipeline(null)} className="sm:flex-1 px-8 py-4 sm:py-6 rounded-[1.5rem] font-black text-[10px] sm:text-xs uppercase tracking-widest text-white/40 hover:bg-white/5 transition-all">Discard</button>
                  <button onClick={() => void savePipelineChanges(!isPersistedCustomPipeline(editingPipeline))} className="sm:flex-[2] btn-apple py-4 sm:py-6 rounded-[1.5rem] font-black text-[10px] sm:text-xs uppercase tracking-[0.4em] shadow-2xl active:scale-95 transition-all">{saving ? 'Saving...' : (isPersistedCustomPipeline(editingPipeline) ? 'Save Changes' : 'Save As Custom Copy')}</button>
              </div>
          </div>
        </div>
      )}

      {/* Node Config Modal */}
      {editingNode && editingPipeline && (
        <div className="fixed inset-0 z-[1300] bg-black/90 flex items-center justify-center p-6 backdrop-blur-3xl">
          <div className="glass w-full max-w-2xl rounded-[4rem] overflow-hidden flex flex-col border-2 border-white/10 shadow-2xl">
              <div className="p-10 border-b border-white/10 flex justify-between items-center bg-white/[0.02]">
                  <div className="space-y-1">
                      <h2 className="font-black tracking-[0.5em] uppercase text-[10px] opacity-40">Node Calibration</h2>
                      <h3 className="text-2xl font-black tracking-tighter text-white uppercase">{editingNode.type} Process</h3>
                  </div>
                  <button onClick={() => setEditingNode(null)} className="w-12 h-12 rounded-2xl glass-dark flex items-center justify-center text-xl">✕</button>
              </div>
              <div className="p-10 space-y-8 flex-1 overflow-y-auto">
                  {editingNode.type === 'vision' && (
                    <div className="space-y-8">
                      <div className="space-y-3">
                          <label className="label-apple">Engine Override</label>
                          <div className="relative">
                              <select 
                                value={editingPipeline.schema.vision_model?.default || ''} 
                                onChange={e => setEditingPipeline({...editingPipeline, schema: {...editingPipeline.schema, vision_model: {default: e.target.value}}})} 
                                className="w-full bg-white/5 border border-white/10 rounded-2xl p-5 text-sm font-black text-white appearance-none cursor-pointer"
                              >
                                  {models.map(m => (
                                      <option key={m} value={m} className="bg-black text-white">{m.split('/')[1] || m}</option>
                                  ))}
                              </select>
                              <span className="absolute right-6 top-6 opacity-20 pointer-events-none">▼</span>
                          </div>
                      </div>
                      <div className="space-y-3">
                          <label className="label-apple">Instruction Set</label>
                          <textarea 
                            value={getVisionPrompt(editingPipeline)} 
                            onChange={e => setEditingPipeline(setVisionPrompt(editingPipeline, e.target.value))} 
                            className="w-full h-80 bg-black/60 border border-white/10 rounded-[2rem] p-6 text-[14px] font-mono text-white/80 leading-relaxed no-scrollbar" 
                          />
                      </div>
                    </div>
                  )}
                  {editingNode.type === 'refine' && (
                    <div className="space-y-3">
                        <label className="label-apple">Merge logic instructions</label>
                        <textarea 
                          value={editingPipeline.schema.refine_prompt?.default || ''} 
                          onChange={e => setEditingPipeline({...editingPipeline, schema: {...editingPipeline.schema, refine_prompt: {default: e.target.value}}})} 
                          className="w-full h-80 bg-black/60 border border-white/10 rounded-[2rem] p-6 text-[14px] font-mono text-white/80 leading-relaxed no-scrollbar" 
                        />
                    </div>
                  )}
                  {editingNode.type === 'scrape' && (
                    <div className="space-y-3">
                        <label className="label-apple">JavaScript Wait Time (ms)</label>
                        <input 
                          type="number" 
                          value={editingPipeline.schema.scrape_wait_time?.default || 2000} 
                          onChange={e => setEditingPipeline({...editingPipeline, schema: {...editingPipeline.schema, scrape_wait_time: {default: parseInt(e.target.value)}}})} 
                          className="w-full bg-white/5 border border-white/10 rounded-2xl p-5 text-sm font-black text-white" 
                        />
                    </div>
                  )}
                  {['barcode', 'search'].includes(editingNode.type) && (
                    <div className="py-20 text-center space-y-4 opacity-20">
                        <span className="text-6xl">⚙️</span>
                        <p className="text-xs font-black uppercase tracking-[0.4em]">Node calibrated by system core</p>
                    </div>
                  )}
              </div>
              <div className="p-10 border-t border-white/10 bg-black/20 text-center">
                  <button onClick={() => setEditingNode(null)} className="btn-apple px-16 py-6 text-[10px] font-black uppercase tracking-widest shadow-2xl">Confirm Parameters</button>
              </div>
          </div>
        </div>
      )}
    </div>
  );
}
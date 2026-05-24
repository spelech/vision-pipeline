import { useState, useEffect } from 'react';

export interface Pipeline {
  id: string;
  name: string;
  schema: {
    active_nodes: { default: string[] };
    vision_model?: { default: string };
    vision_prompt?: { default: string };
    refine_prompt?: { default: string };
    scrape_wait_time?: { default: number };
  };
}

export function PipelineEditor() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [editingPipeline, setEditingPipeline] = useState<Pipeline | null>(null);
  const [editingNode, setEditingNode] = useState<{type: string, index: number} | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

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
      const resp = await fetch('/api/config');
      const data = await resp.json();
      if (data.model_favorites) setModels(data.model_favorites);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
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

  const savePipelineChanges = async () => {
    if (!editingPipeline) return;
    setSaving(true);
    
    // Merge new pipeline into custom_pipelines. 
    // Wait, first we need to fetch all custom_pipelines from config and append/update.
    try {
      const cRes = await fetch('/api/config');
      const cData = await cRes.json();
      let custom = cData.custom_pipelines || [];
      
      const idx = custom.findIndex((p: any) => p.id === editingPipeline.id);
      if (idx !== -1) {
        custom[idx] = editingPipeline;
      } else {
        custom.push(editingPipeline);
      }

      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ custom_pipelines: custom })
      });
      
      setEditingPipeline(null);
      fetchPipelines();
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
    const nodes = [...update.schema.active_nodes.default];
    const target = index + dir;
    if (target < 0 || target >= nodes.length) return;
    
    const temp = nodes[index];
    nodes[index] = nodes[target];
    nodes[target] = temp;
    update.schema.active_nodes.default = nodes;
    setEditingPipeline(update);
  };

  const removeNode = (index: number) => {
    if (!editingPipeline) return;
    const update = { ...editingPipeline };
    update.schema.active_nodes.default.splice(index, 1);
    setEditingPipeline(update);
  };

  const addNode = (type: string) => {
    if (!editingPipeline) return;
    const update = { ...editingPipeline };
    update.schema.active_nodes.default.push(type);
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

      <div className="grid grid-cols-1 gap-6">
        {pipelines.map(p => (
          <div key={p.id} className="glass p-8 rounded-[3rem] space-y-10 group hover:border-white/20 transition-all border-2 border-white/5">
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-8">
                  <div className="space-y-1">
                      <h3 className="text-3xl font-black tracking-tighter text-white">{p.name}</h3>
                      <p className="text-[11px] uppercase text-white/20">{p.id === 'default' ? 'Core Sequence' : 'Custom Flow'}</p>
                  </div>
                  {p.id !== 'default' && (
                    <button onClick={() => setEditingPipeline({ ...p })} className="btn-apple px-10 py-4 rounded-xl text-[10px] font-black uppercase tracking-widest shadow-xl">Configure sequence</button>
                  )}
              </div>

              <div className="relative py-4">
                  <div className="flex flex-col md:flex-row md:items-center gap-6 md:gap-8 overflow-x-auto no-scrollbar pb-6">
                      {(p.schema.active_nodes?.default || ['barcode', 'vision', 'search', 'refine']).map((node, index, arr) => (
                          <div key={index} className="flex flex-col md:flex-row items-center gap-6">
                              <div className="w-full md:w-auto glass-dark px-10 py-6 rounded-[2rem] border border-white/10 min-w-[180px] text-center bg-black/40">
                                  <span className="text-[10px] block font-black uppercase text-white/20 mb-2 tracking-widest">STAGE {index + 1}</span>
                                  <span className="text-[13px] font-black uppercase tracking-[0.2em] text-white/90">{node}</span>
                              </div>
                              {index < arr.length - 1 && (
                                <>
                                  <span className="text-white/20 text-3xl font-thin hidden md:block opacity-60">→</span>
                                  <span className="text-white/20 text-2xl font-thin md:hidden block self-center opacity-60">↓</span>
                                </>
                              )}
                          </div>
                      ))}
                  </div>
              </div>
          </div>
        ))}
      </div>

      {/* Editing Modal */}
      {editingPipeline && (
        <div className="fixed inset-0 z-[1200] bg-black/90 flex items-center justify-center p-6 backdrop-blur-3xl">
          <div className="glass w-full max-w-4xl rounded-[4rem] overflow-hidden flex flex-col max-h-full border-2 border-white/10 shadow-2xl">
              <div className="p-10 border-b border-white/10 flex justify-between items-center bg-white/[0.02]">
                  <div className="space-y-1">
                      <h2 className="font-black tracking-[0.5em] uppercase text-[10px] opacity-40">Pipeline Architecture</h2>
                      <h3 className="text-3xl font-black tracking-tighter text-blue-400">{editingPipeline.name}</h3>
                  </div>
                  <button onClick={() => setEditingPipeline(null)} className="w-12 h-12 rounded-2xl glass-dark flex items-center justify-center text-xl active:scale-90 transition-all">✕</button>
              </div>
              
              <div className="p-10 overflow-y-auto no-scrollbar space-y-10">
                  <div className="space-y-4">
                      <label className="label-apple ml-2">Label</label>
                      <input 
                        type="text" 
                        value={editingPipeline.name} 
                        onChange={e => setEditingPipeline({...editingPipeline, name: e.target.value})} 
                        className="w-full bg-white/5 border border-white/10 rounded-[2rem] p-6 text-xl font-black text-white focus:outline-none focus:border-blue-500/50 shadow-inner" 
                      />
                  </div>

                  <div className="space-y-6">
                      <label className="label-apple ml-2">Sequence Configuration (Tap to customize Node)</label>
                      <div className="space-y-3">
                          {editingPipeline.schema.active_nodes.default.map((node, index, arr) => (
                              <div key={`${node}-${index}`} className="flex items-center gap-4 group">
                                  <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-[10px] font-black opacity-20">{index + 1}</div>
                                  <button onClick={() => setEditingNode({type: node, index})} className="flex-1 glass p-5 rounded-2xl flex items-center justify-between border-white/5 hover:border-blue-500/40 transition-all">
                                      <div className="flex items-center gap-4">
                                          <span className="text-2xl">{node === 'barcode' ? '🔍' : (node === 'vision' ? '🤖' : (node === 'search' ? '🌐' : (node === 'scrape' ? '🕸️' : '🧠')))}</span>
                                          <span className="text-sm font-black uppercase tracking-widest text-white">{node}</span>
                                      </div>
                                      <span className="text-[9px] font-black uppercase text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity">Configure Node</span>
                                  </button>
                                  <div className="flex gap-2">
                                      <button onClick={() => moveNode(index, -1)} disabled={index === 0} className="w-10 h-10 glass rounded-xl flex items-center justify-center hover:bg-white/10 disabled:opacity-0">↑</button>
                                      <button onClick={() => moveNode(index, 1)} disabled={index === arr.length - 1} className="w-10 h-10 glass rounded-xl flex items-center justify-center hover:bg-white/10 disabled:opacity-0">↓</button>
                                      <button onClick={() => removeNode(index)} className="w-10 h-10 glass rounded-xl flex items-center justify-center text-red-500/40 hover:text-red-500 transition-colors">✕</button>
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
                                    className="px-6 py-3 rounded-xl bg-white/5 border border-white/10 text-[10px] font-black uppercase tracking-widest hover:bg-white/10 transition-colors"
                                  >
                                    + {type}
                                  </button>
                              ))}
                          </div>
                      </div>
                  </div>
              </div>

              <div className="p-10 border-t border-white/10 flex gap-4 bg-black/40">
                  <button onClick={() => setEditingPipeline(null)} className="flex-1 px-8 py-6 rounded-[1.5rem] font-black text-xs uppercase tracking-widest text-white/40 hover:bg-white/5 transition-all">Discard</button>
                  <button onClick={savePipelineChanges} className="flex-[2] btn-apple py-6 rounded-[1.5rem] font-black text-xs uppercase tracking-[0.4em] shadow-2xl active:scale-95 transition-all">{saving ? 'Saving...' : 'Persist Registry'}</button>
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
                            value={editingPipeline.schema.vision_prompt?.default || ''} 
                            onChange={e => setEditingPipeline({...editingPipeline, schema: {...editingPipeline.schema, vision_prompt: {default: e.target.value}}})} 
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
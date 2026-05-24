import { useState, useEffect } from 'react';

const SECRET_KEYS = [
  "OPENROUTER_API_KEY",
  "SEARXNG_URL",
  "HOMEBOX_API_KEY",
  "HOMEBOX_EMAIL",
  "HOMEBOX_PASSWORD",
  "MEALIE_API_TOKEN",
  "PRICEBUDDY_API_KEY",
  "CHANGEDETECTION_API_KEY"
];

interface ImageOptimization {
  max_dimension: number;
  quality: number;
}

interface PromptTemplate {
  id: string | number;
  name: string;
  prompt: string;
}

export function Settings() {
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [modelFavorites, setModelFavorites] = useState<string[]>([]);
  const [starredModels, setStarredModels] = useState<string[]>([]);
  const [imageOptimization, setImageOptimization] = useState<ImageOptimization>({ max_dimension: 1024, quality: 85 });
  const [promptTemplates, setPromptTemplates] = useState<PromptTemplate[]>([]);
  const [newModelId, setNewModelId] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch('/api/config')
      .then(r => r.json())
      .then(data => {
        const statuses = data.secrets_status || {};
        const loaded: Record<string, string> = {};
        SECRET_KEYS.forEach(key => {
          loaded[key] = statuses[key] ? "********" : "";
        });
        setSecrets(loaded);
        
        if (data.model_favorites) setModelFavorites(data.model_favorites);
        if (data.starred_models) setStarredModels(data.starred_models);
        if (data.image_optimization) setImageOptimization(data.image_optimization);
        if (data.prompt_templates) setPromptTemplates(data.prompt_templates);
      });
  }, []);

  const handleChange = (key: string, value: string) => {
    setSecrets(prev => ({ ...prev, [key]: value }));
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      const payload = {
        model_favorites: modelFavorites,
        starred_models: starredModels,
        image_optimization: imageOptimization,
        prompt_templates: promptTemplates,
        ...secrets
      };
      
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      alert('Settings saved successfully!');
    } catch (e) {
      console.error(e);
      alert('Failed to save settings.');
    } finally {
      setSaving(false);
    }
  };

  const toggleStar = (modelId: string) => {
    setStarredModels(prev => 
      prev.includes(modelId) ? prev.filter(m => m !== modelId) : [...prev, modelId]
    );
  };

  const prettifyTemplate = (index: number) => {
    try {
      setPromptTemplates(prev => {
        const n = [...prev];
        n[index].prompt = n[index].prompt.trim(); 
        return n;
      });
      alert("Formatted template!");
    } catch (e) {
        console.error(e);
    }
  };

  return (
    <div className="space-y-12 pb-32">
      <header>
        <h2 className="text-4xl font-extrabold tracking-tight mb-2">System Settings</h2>
        <p className="text-white/40 font-medium italic">Configure external APIs, vision parameters, models, and prompts.</p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Image Processing */}
        <section className="space-y-6 flex flex-col">
          <label className="label-apple">Image Processing</label>
          <div className="glass p-8 rounded-[2.5rem] space-y-8 flex-1">
            <div className="flex justify-between items-center">
                <span className="text-[11px] font-black uppercase text-white/40 tracking-widest">Res Limit (px)</span>
                <input 
                  type="number" 
                  value={imageOptimization.max_dimension}
                  onChange={(e) => setImageOptimization(prev => ({...prev, max_dimension: parseInt(e.target.value)}))}
                  className="w-24 bg-white/5 border border-white/10 rounded-xl p-3 text-sm text-center font-bold text-white focus:outline-none" 
                />
            </div>
            <div className="space-y-4">
                <div className="flex justify-between text-[10px] font-black uppercase tracking-widest text-white">
                    <span>JPEG Quality</span>
                    <span className="text-blue-400">{imageOptimization.quality}%</span>
                </div>
                <input 
                  type="range" 
                  min="10" 
                  max="100" 
                  value={imageOptimization.quality}
                  onChange={(e) => setImageOptimization(prev => ({...prev, quality: parseInt(e.target.value)}))}
                  className="w-full h-1.5 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500" 
                />
            </div>
          </div>
        </section>

        {/* Model Registry */}
        <section className="space-y-6 flex flex-col">
          <label className="label-apple">Model Registry</label>
          <div className="glass p-8 rounded-[2.5rem] space-y-6 flex-1 flex flex-col">
            <div className="space-y-3 max-h-64 overflow-y-auto no-scrollbar flex-1">
              {modelFavorites.map(m => (
                <div key={m} className="flex items-center justify-between p-4 rounded-xl bg-white/5 border border-white/5">
                    <div className="flex items-center truncate">
                        <button 
                          onClick={() => toggleStar(m)} 
                          className={`mr-3 transition-colors ${starredModels.includes(m) ? 'text-yellow-400' : 'text-white/10 hover:text-white/40'}`}
                        >
                            <span className="text-lg">{starredModels.includes(m) ? '★' : '☆'}</span>
                        </button>
                        <span className="text-[10px] font-black uppercase tracking-widest truncate text-white">{m.split('/')[1] || m}</span>
                    </div>
                    <button 
                      onClick={() => {
                        setModelFavorites(prev => prev.filter(x => x !== m));
                        setStarredModels(prev => prev.filter(x => x !== m));
                      }} 
                      className="text-red-500/40 hover:text-red-500 text-[10px] font-black"
                    >
                      ✕
                    </button>
                </div>
              ))}
            </div>
            <div className="pt-4 border-t border-white/5 space-y-3">
                <span className="text-[9px] font-black uppercase text-white/30">Register New Model ID</span>
                <div className="flex gap-2">
                    <input 
                      type="text" 
                      value={newModelId}
                      onChange={e => setNewModelId(e.target.value)}
                      placeholder="owner/model-name" 
                      className="flex-1 bg-white/5 border border-white/10 rounded-xl p-3 text-sm focus:outline-none text-white" 
                    />
                    <button 
                      onClick={() => {
                        if(newModelId && !modelFavorites.includes(newModelId)) { 
                          setModelFavorites(prev => [...prev, newModelId]); 
                          setNewModelId(''); 
                        }
                      }} 
                      className="btn-apple px-6 rounded-xl text-[10px] font-black uppercase"
                    >
                      Add
                    </button>
                </div>
            </div>
          </div>
        </section>
      </div>

      <section className="space-y-6">
        <label className="label-apple">Secrets & Infrastructure</label>
        <div className="glass rounded-[3rem] p-10 grid grid-cols-1 md:grid-cols-2 gap-8">
          {SECRET_KEYS.map(key => (
            <div key={key} className="flex flex-col gap-2">
              <label className="text-xs font-bold text-white/50 tracking-wider">
                {key.replace(/_/g, ' ')}
              </label>
              <input 
                type={key.includes('PASSWORD') || key.includes('TOKEN') || key.includes('KEY') ? "password" : "text"}
                value={secrets[key] || ""}
                onChange={(e) => handleChange(key, e.target.value)}
                placeholder={`Enter ${key.replace(/_/g, ' ')}`}
                className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              />
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-6">
        <label className="label-apple">Prompt Engineering Suite</label>
        <div className="space-y-8">
          {promptTemplates.map((p, index) => (
            <div key={p.id} className="glass p-8 rounded-[3rem] space-y-6 border border-white/5 hover:border-blue-500/20 transition-all">
               <div className="flex justify-between items-center border-b border-white/5 pb-6">
                  <input 
                    type="text" 
                    value={p.name} 
                    onChange={e => setPromptTemplates(prev => { const n = [...prev]; n[index].name = e.target.value; return n; })}
                    className="bg-transparent border-none p-0 text-xl font-black uppercase text-blue-400 focus:outline-none focus:ring-0 tracking-[0.2em] w-3/4" 
                  />
                  <div className="flex gap-4">
                      <button onClick={() => prettifyTemplate(index)} className="text-blue-500/50 hover:text-blue-400 text-[10px] font-black uppercase tracking-widest transition-colors">Format</button>
                      <button onClick={() => setPromptTemplates(prev => prev.filter(x => x.id !== p.id))} className="text-red-500/40 hover:text-red-500 text-[10px] font-black uppercase tracking-widest transition-colors">Delete</button>
                  </div>
              </div>
              <div className="space-y-3">
                  <span className="text-[9px] font-black uppercase tracking-widest text-white/30 block ml-2">System Instructions</span>
                  <textarea 
                    value={p.prompt} 
                    onChange={e => setPromptTemplates(prev => { const n = [...prev]; n[index].prompt = e.target.value; return n; })}
                    className="w-full h-[24rem] bg-white/5 border border-white/10 rounded-[2rem] p-8 text-sm font-mono text-white/80 focus:outline-none focus:border-blue-500/40 leading-relaxed shadow-inner"
                    spellCheck={false}
                  />
              </div>
            </div>
          ))}
          <button 
            onClick={() => setPromptTemplates(prev => [...prev, {id: Date.now().toString(), name: 'NEW TEMPLATE', prompt: ''}])} 
            className="w-full py-16 rounded-[3rem] border-2 border-dashed border-white/10 hover:border-blue-500/30 text-xs font-black uppercase tracking-[0.5em] text-white/20 hover:text-blue-500 hover:bg-blue-500/5 transition-all flex flex-col items-center justify-center gap-4 group"
          >
              <span className="text-4xl group-hover:scale-110 transition-transform">+</span>
              <span>Initialize Template</span>
          </button>
        </div>
      </section>

      <div className="fixed bottom-10 left-0 w-full flex justify-center z-50 pointer-events-none">
        <button 
          onClick={saveSettings}
          disabled={saving}
          className="btn-apple pointer-events-auto px-16 py-5 text-[11px] font-black uppercase tracking-[0.3em] shadow-2xl disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Apply Full Configuration'}
        </button>
      </div>

    </div>
  );
}
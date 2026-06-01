import { APP_VERSION } from '../version';

import { useState, useEffect } from 'react';
import {
  normalizePromptTemplates,
  derivePromptTemplatesFromPipelines,
  type PromptTemplate,
  type PipelineApiResponse,
} from './settingsUtils';

const SECRET_KEYS = [
  "LLM_BASE_URL",
  "LLM_API_KEY",
  "OPENROUTER_API_KEY",
  "SEARXNG_URL",
  "HOMEBOX_URL",
  "MEALIE_URL",
  "PRICEBUDDY_URL",
  "CHANGEDETECTION_URL",
  "HOMEBOX_USERNAME",
  "HOMEBOX_PASSWORD",
  "MEALIE_API_TOKEN",
  "PRICEBUDDY_API_KEY",
  "CHANGEDETECTION_API_KEY",
  "GWS_CLIENT_ID",
  "GWS_CLIENT_SECRET",
  "GWS_REFRESH_TOKEN",
  "UPCITEMDB_API_KEY",
  "RECEIPT_WRANGLER_URL",
  "RECEIPT_WRANGLER_API_TOKEN",
  "RECEIPT_WRANGLER_API_KEY",
  "RECEIPT_WRANGLER_GROUP_ID",
  "GMAIL_OCR_BACKEND",
  "GMAIL_OCR_VISION_MODEL",
];

interface ImageOptimization {
  max_dimension: number;
  quality: number;
}

interface ModelApiResponse {
  success?: boolean;
  models?: Array<{ id: string }>;
}

export function Settings() {
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [revealSecrets, setRevealSecrets] = useState(false);
  const [modelFavorites, setModelFavorites] = useState<string[]>([]);
  const [starredModels, setStarredModels] = useState<string[]>([]);
  const [imageOptimization, setImageOptimization] = useState<ImageOptimization>({ max_dimension: 1024, quality: 85 });
  const [promptTemplates, setPromptTemplates] = useState<PromptTemplate[]>([]);
  const [newModelId, setNewModelId] = useState("");
  const [saving, setSaving] = useState(false);
  const [templatesFromConfig, setTemplatesFromConfig] = useState(false);
  const [gmailAutoSyncEnabled, setGmailAutoSyncEnabled] = useState(false);
  const [gmailPollIntervalMinutes, setGmailPollIntervalMinutes] = useState(30);
  const [connectingGmail, setConnectingGmail] = useState(false);
  const [gmailAutoSyncQuery, setGmailAutoSyncQuery] = useState(
    'has:attachment (subject:receipt OR subject:"order confirmation" OR subject:invoice)'
  );
  const [gmailAutoSyncMaxResults, setGmailAutoSyncMaxResults] = useState(25);

  useEffect(() => {
    void (async () => {
      try {
        const [configResult, modelsResult, pipelinesResult] = await Promise.allSettled([
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
            return response.json() as Promise<ModelApiResponse>;
          }),
          fetch('/api/pipelines').then(async (response) => {
            if (!response.ok) {
              throw new Error('Failed to load pipelines');
            }
            return response.json() as Promise<PipelineApiResponse>;
          })
        ]);

        const configData = configResult.status === 'fulfilled' ? configResult.value : {};
        const modelsData = modelsResult.status === 'fulfilled' ? modelsResult.value : {};
        const pipelinesData = pipelinesResult.status === 'fulfilled' ? pipelinesResult.value : {};

        const statuses = configData.secrets_status || {};
        const loaded: Record<string, string> = {};
        SECRET_KEYS.forEach(key => {
          if (!statuses[key]) {
            loaded[key] = '';
          } else if (key.includes('URL')) {
            loaded[key] = String(statuses[key]);
          } else {
            loaded[key] = '********';
          }
        });
        setSecrets(loaded);

        const savedFavorites = Array.isArray(configData.model_favorites) ? configData.model_favorites : [];
        const catalogModels = modelsData?.success && Array.isArray(modelsData.models)
          ? modelsData.models.map((m) => m.id)
          : [];
        setModelFavorites(Array.from(new Set([...savedFavorites, ...catalogModels])));

        if (Array.isArray(configData.starred_models)) setStarredModels(configData.starred_models);
        if (configData.image_optimization) setImageOptimization(configData.image_optimization);

        const savedTemplates = normalizePromptTemplates(configData.prompt_templates);
        const derivedTemplates = derivePromptTemplatesFromPipelines(pipelinesData.pipelines);
        setTemplatesFromConfig(savedTemplates.length > 0);
        setPromptTemplates(savedTemplates.length > 0 ? savedTemplates : derivedTemplates);
        setGmailAutoSyncEnabled(Boolean(configData.gmail_auto_sync_enabled));
        setGmailPollIntervalMinutes(Number(configData.gmail_poll_interval_minutes || 30));
        setGmailAutoSyncQuery(
          String(
            configData.gmail_auto_sync_query
              || 'has:attachment (subject:receipt OR subject:"order confirmation" OR subject:invoice)'
          )
        );
        setGmailAutoSyncMaxResults(Number(configData.gmail_auto_sync_max_results || 25));
      } catch (e) {
        console.error(e);
      }
    })();
  }, []);

  const handleChange = (key: string, value: string) => {
    setSecrets(prev => ({ ...prev, [key]: value }));
  };

  const handleRevealSecretsToggle = async (checked: boolean) => {
    setRevealSecrets(checked);
    try {
      const response = await fetch(`/api/config?reveal_secrets=${checked}`);
      if (response.ok) {
        const configData = await response.json();
        const statuses = configData.secrets_status || {};
        const loaded: Record<string, string> = {};
        SECRET_KEYS.forEach(key => {
          if (!statuses[key]) {
            loaded[key] = '';
          } else if (key.includes('URL') || checked) {
            loaded[key] = String(statuses[key]);
          } else {
            loaded[key] = '********';
          }
        });
        setSecrets(loaded);
      }
    } catch (e) {
      console.error(e);
      alert('Failed to update secrets display.');
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      const payload = {
        model_favorites: modelFavorites,
        starred_models: starredModels,
        image_optimization: imageOptimization,
        gmail_auto_sync_enabled: gmailAutoSyncEnabled,
        gmail_poll_interval_minutes: gmailPollIntervalMinutes,
        gmail_auto_sync_query: gmailAutoSyncQuery,
        gmail_auto_sync_max_results: gmailAutoSyncMaxResults,
        ...secrets
      };
      if (templatesFromConfig || promptTemplates.length > 0) {
        Object.assign(payload, { prompt_templates: promptTemplates });
      }
      
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
      setTemplatesFromConfig(true);
      alert("Formatted template!");
    } catch (e) {
        console.error(e);
    }
  };

  const connectGmail = async () => {
    setConnectingGmail(true);
    try {
      const redirectUri = `${window.location.origin}/`;
      const response = await fetch('/api/gmail/auth-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ redirect_uri: redirectUri, state: 'settings-connect' }),
      });
      const payload = await response.json();
      if (!response.ok || !payload?.auth_url) {
        alert(payload?.detail || payload?.error || 'Failed to create Gmail auth URL.');
        return;
      }
      window.open(String(payload.auth_url), '_blank', 'noopener,noreferrer');
    } catch (e) {
      console.error(e);
      alert('Failed to connect Gmail.');
    } finally {
      setConnectingGmail(false);
    }
  };

  return (
    <div className="space-y-12 pb-32">
      <header className="flex justify-between items-end">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight mb-2">System Settings</h2>
          <p className="text-white/40 font-medium italic">Configure external APIs, vision parameters, models, and prompts.</p>
        </div>
        <div className="text-right">
          <span className="text-[10px] font-black uppercase tracking-[0.4em] text-white/20">Version</span>
          <p className="text-lg font-black tracking-tighter text-white/40">{APP_VERSION}</p>
        </div>
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
        <div className="flex justify-between items-center">
          <label className="label-apple">Secrets & Infrastructure</label>
          <label className="flex items-center gap-3 cursor-pointer text-xs font-bold text-white/50 tracking-wider hover:text-white/80 transition-colors">
            <span>Show Hidden Secrets</span>
            <div className="relative">
              <input
                type="checkbox"
                checked={revealSecrets}
                onChange={(e) => void handleRevealSecretsToggle(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
            </div>
          </label>
        </div>
        <div className="glass rounded-[3rem] p-10 grid grid-cols-1 md:grid-cols-2 gap-8">
          {SECRET_KEYS.map(key => (
            <div key={key} className="flex flex-col gap-2">
              <label className="text-xs font-bold text-white/50 tracking-wider">
                {key.replace(/_/g, ' ')}
              </label>
              <input 
                type={
                  (key.includes('PASSWORD') || key.includes('TOKEN') || key.includes('KEY')) && !revealSecrets
                    ? "password" 
                    : "text"
                }
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
        <label className="label-apple">Gmail Auto Sync</label>
        <div className="glass rounded-[3rem] p-10 grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="md:col-span-2 flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-5 py-4">
            <div>
              <p className="text-xs font-bold text-white/70 tracking-wider">Connect Gmail (OAuth)</p>
              <p className="text-[10px] text-white/40 mt-1">Launches Google consent flow in a new tab.</p>
            </div>
            <button
              type="button"
              onClick={() => void connectGmail()}
              disabled={connectingGmail}
              className="btn-apple px-5 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest disabled:opacity-50"
            >
              {connectingGmail ? 'Connecting...' : 'Connect Gmail'}
            </button>
          </div>
          <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-5 py-4">
            <label htmlFor="gmail-auto-sync-checkbox" className="text-xs font-bold text-white/70 tracking-wider">Enable Background Sync</label>
            <input
              id="gmail-auto-sync-checkbox"
              type="checkbox"
              checked={gmailAutoSyncEnabled}
              onChange={(e) => setGmailAutoSyncEnabled(e.target.checked)}
              className="h-5 w-5"
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-xs font-bold text-white/50 tracking-wider">Poll Interval (minutes)</label>
            <input
              type="number"
              min={1}
              max={1440}
              value={gmailPollIntervalMinutes}
              onChange={(e) => setGmailPollIntervalMinutes(Number(e.target.value) || 30)}
              className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-4 text-sm text-white focus:outline-none"
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-xs font-bold text-white/50 tracking-wider">Auto Sync Max Results</label>
            <input
              type="number"
              min={1}
              max={100}
              value={gmailAutoSyncMaxResults}
              onChange={(e) => setGmailAutoSyncMaxResults(Number(e.target.value) || 25)}
              className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-4 text-sm text-white focus:outline-none"
            />
          </div>
          <div className="flex flex-col gap-2 md:col-span-2">
            <label className="text-xs font-bold text-white/50 tracking-wider">Auto Sync Query</label>
            <input
              type="text"
              value={gmailAutoSyncQuery}
              onChange={(e) => setGmailAutoSyncQuery(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-4 text-sm text-white focus:outline-none"
            />
          </div>
        </div>
      </section>

      <section className="space-y-6">
        <label className="label-apple">Prompt Engineering Suite</label>
        <div className="space-y-8">
          {promptTemplates.length === 0 && (
            <div className="glass p-8 rounded-[3rem] border border-white/5 text-sm text-white/40">
              No prompt templates are currently saved. Pipeline prompt defaults will appear here once available or after you save templates.
            </div>
          )}
          {promptTemplates.map((p, index) => (
            <div key={p.id} className="glass p-8 rounded-[3rem] space-y-6 border border-white/5 hover:border-blue-500/20 transition-all">
               <div className="flex justify-between items-center border-b border-white/5 pb-6">
                  <input 
                    type="text" 
                    value={p.name} 
                    onChange={e => {
                      setTemplatesFromConfig(true);
                      setPromptTemplates(prev => {
                        const n = [...prev];
                        n[index].name = e.target.value;
                        return n;
                      });
                    }}
                    className="bg-transparent border-none p-0 text-xl font-black uppercase text-blue-400 focus:outline-none focus:ring-0 tracking-[0.2em] w-3/4" 
                  />
                  <div className="flex gap-4">
                      <button onClick={() => prettifyTemplate(index)} className="text-blue-500/50 hover:text-blue-400 text-[10px] font-black uppercase tracking-widest transition-colors">Format</button>
                      <button onClick={() => {
                        setTemplatesFromConfig(true);
                        setPromptTemplates(prev => prev.filter(x => x.id !== p.id));
                      }} className="text-red-500/40 hover:text-red-500 text-[10px] font-black uppercase tracking-widest transition-colors">Delete</button>
                  </div>
              </div>
              <div className="space-y-3">
                  <span className="text-[9px] font-black uppercase tracking-widest text-white/30 block ml-2">System Instructions</span>
                  <textarea 
                    value={p.prompt} 
                    onChange={e => {
                      setTemplatesFromConfig(true);
                      setPromptTemplates(prev => {
                        const n = [...prev];
                        n[index].prompt = e.target.value;
                        return n;
                      });
                    }}
                    className="w-full h-[18rem] sm:h-[24rem] bg-white/5 border border-white/10 rounded-[1.5rem] sm:rounded-[2rem] p-4 sm:p-8 text-[12px] sm:text-sm font-mono text-white/80 focus:outline-none focus:border-blue-500/40 leading-relaxed shadow-inner"
                    spellCheck={false}
                  />
              </div>
            </div>
          ))}
          <button 
            onClick={() => {
              setTemplatesFromConfig(true);
              setPromptTemplates(prev => [...prev, {id: Date.now().toString(), name: 'NEW TEMPLATE', prompt: ''}]);
            }} 
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
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
  "VISION_MODEL_DEFAULT",
  "REFINE_MODEL_DEFAULT",
];

interface ImageOptimization {
  max_dimension: number;
  quality: number;
}

interface ModelApiResponse {
  success?: boolean;
  models?: Array<{ id: string }>;
}

interface ServicePromptConfig {
  model?: string;
  system_prompt?: string;
  user_prompt?: string;
  [key: string]: unknown;
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
  const [scanning, setScanning] = useState(false);
  const [scanResults, setScanResults] = useState<{
    success: boolean;
    discovered_urls: Record<string, string>;
    error?: string;
  } | null>(null);

  // Setup Guide Tabs and LLM provider states
  const [activeTab, setActiveTab] = useState<'setup' | 'general' | 'prompts'>('setup');
  const [llmProvider, setLlmProvider] = useState<'openrouter' | 'litellm'>('openrouter');
  const [secretsSources, setSecretsSources] = useState<Record<string, string>>({});
  const [servicePrompts, setServicePrompts] = useState<Record<string, ServicePromptConfig>>({});

  const runAutodiscover = async () => {
    setScanning(true);
    setScanResults(null);
    try {
      const response = await fetch('/api/config/discover');
      if (!response.ok) throw new Error('Discovery failed');
      const data = await response.json();
      setScanResults(data);
    } catch (e) {
      console.error(e);
      setScanResults({
        success: false,
        discovered_urls: {},
        error: String(e)
      });
    } finally {
      setScanning(false);
    }
  };

  const applyDiscovered = () => {
    if (!scanResults) return;
    setSecrets(prev => ({
      ...prev,
      ...scanResults.discovered_urls
    }));
    alert('Discovered settings applied to form! Click "Apply Full Configuration" at the bottom to save permanently.');
  };

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
          } else if (key.includes('URL') || key.includes('MODEL')) {
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
        if (configData.secrets_sources) setSecretsSources(configData.secrets_sources);
        if (configData.service_prompts) setServicePrompts(configData.service_prompts);

        // Derive active LLM provider mode
        const hasLlmBaseUrl = !!statuses['LLM_BASE_URL'];
        setLlmProvider(hasLlmBaseUrl ? 'litellm' : 'openrouter');

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
          } else if (key.includes('URL') || checked || key.includes('MODEL')) {
            loaded[key] = String(statuses[key]);
          } else {
            loaded[key] = '********';
          }
        });
        setSecrets(loaded);
        if (configData.secrets_sources) setSecretsSources(configData.secrets_sources);
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
        service_prompts: servicePrompts,
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
      
      // Reload config sources to reflect saved state
      const response = await fetch(`/api/config?reveal_secrets=${revealSecrets}`);
      if (response.ok) {
        const configData = await response.json();
        if (configData.secrets_sources) setSecretsSources(configData.secrets_sources);
      }
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

  const exportConfig = async () => {
    try {
      const response = await fetch('/api/config/export');
      if (!response.ok) throw new Error('Export failed');
      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `vision-pipeline-config-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
      alert('Failed to export configuration.');
    }
  };

  const importConfig = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const data = JSON.parse(e.target?.result as string);
        if (!confirm('This will overwrite current settings and custom pipelines. Continue?')) return;

        const response = await fetch('/api/config/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        });

        if (response.ok) {
          alert('Configuration imported successfully! Reloading...');
          window.location.reload();
        } else {
          const err = await response.json();
          alert(`Import failed: ${err.detail || 'Unknown error'}`);
        }
      } catch (err) {
        console.error(err);
        alert('Invalid JSON file.');
      }
    };
    reader.readAsText(file);
    // Reset input
    event.target.value = '';
  };

  const getMissingDbSettings = () => {
    const missing: string[] = [];
    if (llmProvider === 'openrouter') {
      if (secretsSources['OPENROUTER_API_KEY'] !== 'database') missing.push('OPENROUTER_API_KEY');
    } else {
      if (secretsSources['LLM_BASE_URL'] !== 'database') missing.push('LLM_BASE_URL');
    }
    if (secretsSources['VISION_MODEL_DEFAULT'] !== 'database') missing.push('VISION_MODEL_DEFAULT');
    if (secretsSources['REFINE_MODEL_DEFAULT'] !== 'database') missing.push('REFINE_MODEL_DEFAULT');

    if (secrets['HOMEBOX_URL'] && secretsSources['HOMEBOX_USERNAME'] !== 'database') missing.push('HOMEBOX_USERNAME');
    if (secrets['HOMEBOX_URL'] && secretsSources['HOMEBOX_PASSWORD'] !== 'database') missing.push('HOMEBOX_PASSWORD');
    if (secrets['MEALIE_URL'] && secretsSources['MEALIE_API_TOKEN'] !== 'database') missing.push('MEALIE_API_TOKEN');
    if (secrets['PRICEBUDDY_URL'] && secretsSources['PRICEBUDDY_API_KEY'] !== 'database') missing.push('PRICEBUDDY_API_KEY');
    if (secrets['CHANGEDETECTION_URL'] && secretsSources['CHANGEDETECTION_API_KEY'] !== 'database') missing.push('CHANGEDETECTION_API_KEY');

    if (gmailAutoSyncEnabled) {
      if (secretsSources['GWS_CLIENT_ID'] !== 'database') missing.push('GWS_CLIENT_ID');
      if (secretsSources['GWS_CLIENT_SECRET'] !== 'database') missing.push('GWS_CLIENT_SECRET');
      if (secretsSources['GWS_REFRESH_TOKEN'] !== 'database') missing.push('GWS_REFRESH_TOKEN');
    }
    return missing;
  };
  const missingDbSettings = getMissingDbSettings();

  const INFRA_SECRET_KEYS = SECRET_KEYS.filter(key => 
    key !== 'LLM_BASE_URL' && 
    key !== 'LLM_API_KEY' && 
    key !== 'OPENROUTER_API_KEY' && 
    key !== 'VISION_MODEL_DEFAULT' && 
    key !== 'REFINE_MODEL_DEFAULT'
  );

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

      {/* Tabs Selection */}
      <div className="flex flex-wrap gap-3 border-b border-white/10 pb-4 mb-6">
        <button
          type="button"
          onClick={() => setActiveTab('setup')}
          className={`px-6 py-3 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${
            activeTab === 'setup'
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20'
              : 'bg-white/5 hover:bg-white/10 text-white/60'
          }`}
        >
          Setup Guide
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('general')}
          className={`px-6 py-3 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${
            activeTab === 'general'
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20'
              : 'bg-white/5 hover:bg-white/10 text-white/60'
          }`}
        >
          General Config
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('prompts')}
          className={`px-6 py-3 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${
            activeTab === 'prompts'
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20'
              : 'bg-white/5 hover:bg-white/10 text-white/60'
          }`}
        >
          Prompt Suite
        </button>

        <label className="flex items-center gap-3 cursor-pointer text-xs font-bold text-white/50 tracking-wider hover:text-white/80 transition-colors ml-auto">
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

      {/* Tab 1: Setup Guide */}
      {activeTab === 'setup' && (
        <div className="space-y-8 animate-fade-in">
          {/* Database Settings Warning */}
          {missingDbSettings.length > 0 && (
            <div className="glass p-6 rounded-[2rem] border border-yellow-500/25 bg-yellow-500/5 text-yellow-200/90 text-sm space-y-2">
              <div className="flex items-center gap-3 font-extrabold uppercase tracking-wider text-xs">
                <span className="text-xl">⚠️</span> Database Settings Warning
              </div>
              <p className="text-xs font-medium">
                The following required settings are not configured in the database:
              </p>
              <div className="flex flex-wrap gap-2 pt-1">
                {missingDbSettings.map(key => (
                  <span key={key} className="bg-yellow-500/10 border border-yellow-500/20 rounded-md px-2 py-0.5 font-mono text-[10px] font-bold">
                    {key}
                  </span>
                ))}
              </div>
              <p className="text-[10px] text-yellow-200/50 italic pt-1">
                The application will try to use host environment variables (e.g. from your .env file) as fallbacks, but they should be configured in the database for single source of truth.
              </p>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* LLM Gateway Provider Card */}
            <div className="glass p-8 rounded-[2.5rem] space-y-6 flex flex-col justify-between">
              <div>
                <label className="label-apple mb-4 block">LLM Gateway Provider</label>
                <div className="grid grid-cols-2 gap-4">
                  <button
                    type="button"
                    onClick={() => {
                      setLlmProvider('openrouter');
                      handleChange('LLM_BASE_URL', '');
                    }}
                    className={`p-6 rounded-[1.5rem] border text-left transition-all flex flex-col justify-between h-36 ${
                      llmProvider === 'openrouter'
                        ? 'bg-blue-600/10 border-blue-500/50 shadow-inner'
                        : 'bg-white/5 border-white/5 hover:bg-white/10'
                    }`}
                  >
                    <span className="text-md font-extrabold text-white">OpenRouter</span>
                    <span className="text-[10px] text-white/50 leading-relaxed mt-2">
                      Use cloud models (Qwen, Gemini, Claude) via OpenRouter.ai gateway.
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setLlmProvider('litellm');
                      if (!secrets['LLM_BASE_URL']) {
                        handleChange('LLM_BASE_URL', 'http://localhost:4000/v1');
                      }
                    }}
                    className={`p-6 rounded-[1.5rem] border text-left transition-all flex flex-col justify-between h-36 ${
                      llmProvider === 'litellm'
                        ? 'bg-blue-600/10 border-blue-500/50 shadow-inner'
                        : 'bg-white/5 border-white/5 hover:bg-white/10'
                    }`}
                  >
                    <span className="text-md font-extrabold text-white">LiteLLM / Custom</span>
                    <span className="text-[10px] text-white/50 leading-relaxed mt-2">
                      Use a local or custom LiteLLM proxy, Ollama, or OpenAI gateway.
                    </span>
                  </button>
                </div>
              </div>

              {/* Provider Fields */}
              <div className="space-y-4 pt-4 border-t border-white/5">
                {llmProvider === 'openrouter' ? (
                  <div className="flex flex-col gap-2">
                    <label className="text-xs font-bold text-white/50 tracking-wider">
                      OPENROUTER_API_KEY
                    </label>
                    <input
                      type={revealSecrets ? 'text' : 'password'}
                      value={secrets['OPENROUTER_API_KEY'] || ''}
                      onChange={e => handleChange('OPENROUTER_API_KEY', e.target.value)}
                      placeholder="Enter OPENROUTER API KEY"
                      className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                    />
                  </div>
                ) : (
                  <>
                    <div className="flex flex-col gap-2">
                      <label className="text-xs font-bold text-white/50 tracking-wider">
                        LLM_BASE_URL
                      </label>
                      <input
                        type="text"
                        value={secrets['LLM_BASE_URL'] || ''}
                        onChange={e => handleChange('LLM_BASE_URL', e.target.value)}
                        placeholder="http://localhost:4000/v1"
                        className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <label className="text-xs font-bold text-white/50 tracking-wider">
                        LLM_API_KEY (Optional)
                      </label>
                      <input
                        type={revealSecrets ? 'text' : 'password'}
                        value={secrets['LLM_API_KEY'] || ''}
                        onChange={e => handleChange('LLM_API_KEY', e.target.value)}
                        placeholder="Enter API Key or token"
                        className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                      />
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Model Role Assignments Card */}
            <div className="glass p-8 rounded-[2.5rem] space-y-6">
              <label className="label-apple">Model Role Assignments</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <label className="text-xs font-bold text-white/50 tracking-wider">Default Vision Model</label>
                  <select
                    value={secrets['VISION_MODEL_DEFAULT'] || ''}
                    onChange={e => handleChange('VISION_MODEL_DEFAULT', e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-4 text-xs text-white focus:outline-none cursor-pointer"
                  >
                    <option value="" className="bg-neutral-900">Select model...</option>
                    {modelFavorites.map(m => (
                      <option key={m} value={m} className="bg-neutral-900">{m}</option>
                    ))}
                  </select>
                </div>

                <div className="flex flex-col gap-2">
                  <label className="text-xs font-bold text-white/50 tracking-wider">Default Refine Model</label>
                  <select
                    value={secrets['REFINE_MODEL_DEFAULT'] || ''}
                    onChange={e => handleChange('REFINE_MODEL_DEFAULT', e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-4 text-xs text-white focus:outline-none cursor-pointer"
                  >
                    <option value="" className="bg-neutral-900">Select model...</option>
                    {modelFavorites.map(m => (
                      <option key={m} value={m} className="bg-neutral-900">{m}</option>
                    ))}
                  </select>
                </div>

                {['homebox', 'mealie', 'pricebuddy', 'changedetection'].map(service => (
                  <div key={service} className="flex flex-col gap-2">
                    <label className="text-xs font-bold text-white/50 tracking-wider">
                      {service.charAt(0).toUpperCase() + service.slice(1)} Model
                    </label>
                    <select
                      value={servicePrompts[service]?.model || ''}
                      onChange={e => {
                        const val = e.target.value;
                        setServicePrompts(prev => ({
                          ...prev,
                          [service]: {
                            ...prev[service],
                            model: val
                          }
                        }));
                      }}
                      className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-4 text-xs text-white focus:outline-none cursor-pointer"
                    >
                      <option value="" className="bg-neutral-900">Use default refine model</option>
                      {modelFavorites.map(m => (
                        <option key={m} value={m} className="bg-neutral-900">{m}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>

            {/* Visual Variables Table */}
            <div className="glass p-8 rounded-[2.5rem] space-y-6 md:col-span-2">
              <label className="label-apple">Infrastructure & API Secrets</label>
              <p className="text-[10px] text-white/40 italic">Manage external service endpoints and passwords. Clear any field and save to fall back to host environment variables.</p>
              <div className="space-y-4">
                {INFRA_SECRET_KEYS.map(key => {
                  const source = secretsSources[key] || 'none';
                  return (
                    <div key={key} className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-2xl bg-white/5 border border-white/5 hover:border-white/10 transition-colors">
                      <div className="md:w-1/3 space-y-1">
                        <span className="text-xs font-bold text-white/80">{key.replace(/_/g, ' ')}</span>
                        <div className="flex gap-2">
                          {source === 'database' ? (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[9px] font-bold bg-green-500/10 text-green-400 border border-green-500/20">
                              Database Active
                            </span>
                          ) : source === 'environment' ? (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[9px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                              Env Fallback
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[9px] font-bold bg-white/5 text-white/30 border border-white/5">
                              Not Configured
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex-1">
                        <input
                          type={
                            (key.includes('PASSWORD') || key.includes('TOKEN') || key.includes('KEY')) && !revealSecrets
                              ? "password"
                              : "text"
                          }
                          value={secrets[key] || ""}
                          onChange={e => handleChange(key, e.target.value)}
                          placeholder={`Enter ${key.replace(/_/g, ' ')}`}
                          className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-xs text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50"
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: General Config */}
      {activeTab === 'general' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 animate-fade-in">
          {/* Import/Export */}
          <section className="space-y-6 flex flex-col md:col-span-2">
            <label className="label-apple">Backup & Sync</label>
            <div className="glass p-8 rounded-[2.5rem] flex gap-4 items-center">
              <button
                onClick={() => void exportConfig()}
                className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-black uppercase tracking-widest px-8 py-4 rounded-2xl transition-all shadow-lg shadow-blue-900/20"
              >
                Export Configuration
              </button>
              <div className="relative">
                <input
                  type="file"
                  accept=".json"
                  onChange={(e) => void importConfig(e)}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <button
                  className="bg-white/5 hover:bg-white/10 text-white/70 text-xs font-black uppercase tracking-widest px-8 py-4 rounded-2xl border border-white/10 transition-all"
                >
                  Import Configuration
                </button>
              </div>
              <p className="text-[10px] text-white/30 italic ml-auto max-w-[200px] text-right">
                Sync prompts, pipelines, and secrets between dev and production environments.
              </p>
            </div>
          </section>

          {/* Autodiscovery */}
          <section className="space-y-6 flex flex-col md:col-span-2">
            <label className="label-apple">Environment Autodiscovery</label>
            <div className="glass p-8 rounded-[2.5rem] space-y-6">
              <div className="flex gap-4 items-center">
                <button
                  type="button"
                  onClick={() => void runAutodiscover()}
                  disabled={scanning}
                  className="bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-black uppercase tracking-widest px-8 py-4 rounded-2xl transition-all shadow-lg shadow-purple-900/20"
                >
                  {scanning ? 'Scanning Network...' : 'Scan Local Environment'}
                </button>
                <p className="text-[10px] text-white/30 italic max-w-[300px]">
                  Detect other Docker containers on your network (Mealie, Homebox, SearxNG, etc.) using safe hostname probes.
                </p>
              </div>

              {scanResults && (
                <div className="pt-6 border-t border-white/5 space-y-4">
                  <div className="max-w-md">
                    {/* Services discovered */}
                    <div className="space-y-3">
                      <span className="text-[10px] font-black uppercase tracking-widest text-white/40 block">Discovered Services</span>
                      {Object.keys(scanResults.discovered_urls).length === 0 ? (
                         <p className="text-xs text-white/30 italic">No services detected on standard container names or ports.</p>
                      ) : (
                        <div className="space-y-2">
                          {Object.entries(scanResults.discovered_urls).map(([key, val]) => (
                            <div key={key} className="flex items-center gap-2 text-xs bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                              <span className="text-green-400">✓</span>
                              <span className="font-bold text-white/85">{key.replace('_URL', '')}</span>
                              <span className="text-[10px] font-mono text-white/40 truncate ml-auto">{val}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {Object.keys(scanResults.discovered_urls).length > 0 && (
                    <div className="flex justify-end pt-4">
                      <button
                        type="button"
                        onClick={applyDiscovered}
                        className="bg-white/10 hover:bg-white/20 text-white text-xs font-black uppercase tracking-widest px-6 py-3 rounded-xl border border-white/10 transition-all"
                      >
                        Apply Discovered Settings
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>

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

          {/* Gmail Sync Section */}
          <section className="space-y-6 md:col-span-2">
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
        </div>
      )}

      {/* Tab 3: Prompts Suite */}
      {activeTab === 'prompts' && (
        <section className="space-y-6 animate-fade-in">
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
      )}

      {/* Floating Save Button */}
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
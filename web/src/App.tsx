import React, { useState, useEffect, useCallback } from 'react';
import { Camera } from 'lucide-react';
import type { Asset } from './types';
import { Navbar } from './components/Navbar';
import { AssetCard } from './components/AssetCard';
import { Dashboard } from './components/Dashboard';
import { PreviewModal } from './components/PreviewModal';
import { Settings } from './components/Settings';
import { NetworkCheck } from './components/NetworkCheck';

import { PipelineEditor } from './components/PipelineEditor';

export default function App() {
  const [queue, setQueue] = useState<Asset[]>([]);
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('review');
  const [previewItem, setPreviewItem] = useState<{item: Asset, service: string, payload: Record<string, unknown>} | null>(null);

  const fetchQueue = useCallback(async () => {
    try {
      setLoading(true);
      const resp = await fetch('/api/queue');
      const data = await resp.json();
      setQueue(data.items || []);
    } catch (e) {
      console.error('Failed to fetch queue', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchQueue();
  }, [fetchQueue]);

  const toggleSelection = (id: string) => {
    setSelectedItems(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
  };

  const selectAll = () => {
    if (selectedItems.length === queue.length) {
      setSelectedItems([]);
    } else {
      setSelectedItems(queue.map(i => i.id));
    }
  };

  const handleBulkApprove = async () => {
    if (!selectedItems.length) return;
    setLoading(true);
    try {
      const resp = await fetch('/api/bulk-approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_ids: selectedItems })
      });
      if (resp.ok) {
        setQueue(q => q.filter(i => !selectedItems.includes(i.id)));
        setSelectedItems([]);
      }
    } catch (e) {
      console.error('Bulk approve failed', e);
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async (item: Asset) => {
    const service = item.selected_services[0] || 'homebox';
    try {
      const resp = await fetch(`/api/preview/${service}?item_id=${item.id}`);
      const data = await resp.json();
      setPreviewItem({ item, service, payload: data.payload });
    } catch (e) {
      console.error('Preview failed', e);
    }
  };

  const executeItem = async (item: Asset, overrides?: Record<string, unknown>) => {
    try {
      const resp = await fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: item.id,
          service_names: item.selected_services,
          overrides: overrides || item.edit_data
        })
      });
      if (resp.ok) {
        setQueue(q => q.filter(i => i.id !== item.id));
        setPreviewItem(null);
      }
    } catch (e) {
      console.error('Execution failed', e);
    }
  };

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setLoading(true);
    
    try {
      if (files.length === 1) {
        const formData = new FormData();
        formData.append('file', files[0]);
        formData.append('pipeline_id', 'default');
        formData.append('settings', '{}');
        
        const resp = await fetch('/api/identify', {
          method: 'POST',
          body: formData,
        });
        if (resp.ok) {
          await fetchQueue();
          setActiveTab('review');
        }
      } else {
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
          formData.append('files', files[i]);
        }
        formData.append('pipeline_id', 'default');
        
        const resp = await fetch('/api/batch-upload', {
          method: 'POST',
          body: formData,
        });
        if (resp.ok) {
          await fetchQueue();
          setActiveTab('review');
        }
      }
    } catch (e) {
      console.error('Upload failed', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white selection:bg-blue-500/30 font-sans">
      <NetworkCheck />
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="max-w-7xl mx-auto pt-32 px-6 pb-20">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
          <div className="lg:col-span-8 space-y-8">
            {activeTab === 'review' ? (
              <>
                <header className="flex justify-between items-end">
                  <div>
                    <h2 className="text-4xl font-extrabold tracking-tight mb-2">Review Queue</h2>
                    <p className="text-white/40 font-medium italic">Vibe-coding the future of asset ingestion.</p>
                  </div>
                  <button 
                    onClick={fetchQueue} 
                    className="bg-white/5 hover:bg-white/10 px-4 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase"
                  >
                    Sync DB
                  </button>
                </header>

                <div className="space-y-4">
                  {loading ? (
                    <div className="py-20 flex justify-center">
                      <div className="w-8 h-8 border-2 border-white/10 border-t-white rounded-full animate-spin" />
                    </div>
                  ) : queue.length === 0 ? (
                    <div className="py-20 text-center glass rounded-[2rem]">
                      <p className="text-white/30 text-sm font-medium">Waiting for assets to ingest...</p>
                    </div>
                  ) : (
                    <>
                      <div className="flex justify-between items-center px-4">
                        <label htmlFor="selectAll" className="flex items-center gap-3 cursor-pointer group">
                          <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${selectedItems.length === queue.length ? 'bg-blue-500 border-blue-500' : 'border-white/30 group-hover:border-white/50'}`}>
                            {selectedItems.length === queue.length && <div className="w-2.5 h-2.5 bg-white rounded-[2px]" />}
                          </div>
                          <span className="text-sm font-bold text-white/70 group-hover:text-white transition-colors">Select All</span>
                        </label>
                        {selectedItems.length > 0 && (
                          <button 
                            onClick={handleBulkApprove} 
                            className="bg-green-600 hover:bg-green-500 px-4 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase transition-all shadow-lg shadow-green-600/20"
                          >
                            Approve {selectedItems.length} Items
                          </button>
                        )}
                      </div>
                      <input 
                        type="checkbox" 
                        className="hidden" 
                        checked={selectedItems.length === queue.length} 
                        onChange={selectAll} 
                        id="selectAll" 
                      />
                      {queue.map(item => (
                        <AssetCard 
                          key={item.id} 
                          item={item} 
                          isSelected={selectedItems.includes(item.id)}
                          onToggleSelect={() => toggleSelection(item.id)}
                          onPreview={() => handlePreview(item)} 
                          onExecute={(overrides) => executeItem(item, overrides)} 
                        />
                      ))}
                    </>
                  )}
                </div>
              </>
            ) : activeTab === 'identify' ? (
              <div className="space-y-8">
                <header>
                  <h2 className="text-4xl font-extrabold tracking-tight mb-2">Identify Asset</h2>
                  <p className="text-white/40 font-medium italic">Capture or upload an image to begin AI processing.</p>
                </header>
                
                <div className="glass rounded-[3rem] p-12 flex flex-col items-center justify-center border-dashed border-2 border-white/10 hover:border-blue-500/30 transition-all group overflow-hidden relative">
                   <div className="absolute inset-0 bg-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                   <div className="relative z-10 flex flex-col items-center gap-6">
                      <div className="w-20 h-20 bg-blue-600 rounded-3xl flex items-center justify-center shadow-2xl shadow-blue-500/40">
                         <Camera className="w-10 h-10 text-white" />
                      </div>
                      <div className="text-center">
                        <h3 className="text-2xl font-bold mb-2">Drop image here</h3>
                        <p className="text-white/40 text-sm">or click to browse from your device</p>
                      </div>
                      <input 
                        type="file" 
                        onChange={handleUpload}
                        className="absolute inset-0 opacity-0 cursor-pointer" 
                        accept="image/*"
                        multiple
                      />
                   </div>
                </div>
              </div>
            ) : activeTab === 'pipelines' ? (
              <PipelineEditor />
            ) : activeTab === 'system' ? (
              <Settings />
            ) : (
              <div className="py-20 text-center glass rounded-[2rem]">
                <p className="text-white/30 text-sm font-medium">Coming soon...</p>
              </div>
            )}
          </div>

          <Dashboard queueLength={queue.length} onUpload={handleUpload} />
        </div>
      </main>

      {previewItem && (
        <PreviewModal 
          preview={previewItem} 
          onClose={() => setPreviewItem(null)} 
          onConfirm={(overrides) => executeItem(previewItem.item, overrides)}
        />
      )}
    </div>
  );
}


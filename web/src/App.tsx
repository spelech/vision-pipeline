import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Camera } from 'lucide-react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { Asset } from './types';
import { Navbar } from './components/Navbar';
import { AssetCard } from './components/AssetCard';
import { PreviewModal } from './components/PreviewModal';
import { Settings } from './components/Settings';
import { NetworkCheck } from './components/NetworkCheck';

import { PipelineEditor } from './components/PipelineEditor';

interface PipelineSummary {
  id: string;
  name: string;
}

type PipelineStageId = 'barcode' | 'vision' | 'search' | 'refine' | 'sync';

const DEFAULT_PIPELINE_OPTION: PipelineSummary = { id: 'default', name: 'Default Vision Pipeline' };

export default function App() {
  const [queue, setQueue] = useState<Asset[]>([]);
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('identify');
  const [queueStatus, setQueueStatus] = useState<'all' | 'pending' | 'approved' | 'processing'>('all');
  const [previewItem, setPreviewItem] = useState<{item: Asset, service: string, payload: Record<string, unknown>} | null>(null);
  const [pipelines, setPipelines] = useState<PipelineSummary[]>([]);
  const [selectedPipelineId, setSelectedPipelineId] = useState('default');
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [lastIdentifyResult, setLastIdentifyResult] = useState<Asset | null>(null);
  const [toast, setToast] = useState<{message: string, type: 'success' | 'error' | 'info'} | null>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);
  const batchInputRef = useRef<HTMLInputElement>(null);
  const listParentRef = useRef<HTMLDivElement>(null);
  const cameraVideoRef = useRef<HTMLVideoElement>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);

  const [processingFile, setProcessingFile] = useState<File | null>(null);
  const [processingFileUrl, setProcessingFileUrl] = useState<string>('');
  const [processingSessionId, setProcessingSessionId] = useState<string | null>(null);
  const [processingLogs, setProcessingLogs] = useState<string[]>([]);
  const [processingError, setProcessingError] = useState<string | null>(null);

  useEffect(() => {
    if (processingFile) {
      const url = typeof URL !== 'undefined' && URL.createObjectURL ? URL.createObjectURL(processingFile) : '';
      setProcessingFileUrl(url);
      return () => {
        if (url && typeof URL !== 'undefined' && URL.revokeObjectURL) {
          URL.revokeObjectURL(url);
        }
      };
    } else {
      setProcessingFileUrl('');
    }
  }, [processingFile]);

  useEffect(() => {
    if (!processingSessionId) return;

    let isSubscribed = true;
    const pollInterval = setInterval(async () => {
      try {
        const resp = await fetch(`/api/logs/${processingSessionId}`);
        if (!resp.ok) return;
        const data = await resp.json();
        if (isSubscribed && data && Array.isArray(data.logs)) {
          const messages = data.logs.map((l: { message: string }) => l.message);
          setProcessingLogs(messages);
        }
      } catch (err) {
        console.error('Failed to fetch logs', err);
      }
    }, 800);

    return () => {
      isSubscribed = false;
      clearInterval(pollInterval);
    };
  }, [processingSessionId]);

  const fetchQueue = useCallback(async (status: 'all' | 'pending' | 'approved' | 'processing' = 'all') => {
    try {
      setLoading(true);
      const resp = await fetch(`/api/queue?status=${status}`);
      const data = await resp.json();
      setQueue(data.items || []);
    } catch (e) {
      console.error('Failed to fetch queue', e);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchPipelines = useCallback(async () => {
    try {
      const resp = await fetch('/api/pipelines');
      const data = await resp.json();
      if (data.success && Array.isArray(data.pipelines)) {
        const loaded = data.pipelines.map((pipeline: PipelineSummary) => ({ id: pipeline.id, name: pipeline.name }));
        const withDefault = loaded.some((pipeline: PipelineSummary) => pipeline.id === 'default')
          ? loaded
          : [DEFAULT_PIPELINE_OPTION, ...loaded];
        setPipelines(withDefault);
      }
    } catch (e) {
      console.error('Failed to fetch pipelines', e);
      setPipelines([DEFAULT_PIPELINE_OPTION]);
    }
  }, []);

  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    setSelectedItems([]);
    if ((tab === 'identify' || tab === 'batch' || tab === 'pipelines') && pipelines.length === 0) {
      void fetchPipelines();
    }
    if (tab === 'identify') {
      setQueueStatus('pending');
    } else if (tab === 'review') {
      setQueueStatus('all');
    } else if (tab === 'batch') {
      setQueueStatus('processing');
    }
  };

  useEffect(() => {
    void fetchQueue(queueStatus);
  }, [queueStatus, fetchQueue]);

  useEffect(() => {
    void fetchPipelines();
  }, [fetchPipelines]);

  useEffect(() => {
    if (!cameraOpen || !cameraStreamRef.current || !cameraVideoRef.current) {
      return;
    }

    cameraVideoRef.current.srcObject = cameraStreamRef.current;
    void cameraVideoRef.current.play().catch((error) => {
      console.error('Failed to play camera preview', error);
      setCameraError('Unable to start the camera preview.');
    });
  }, [cameraOpen]);

  useEffect(() => () => {
    cameraStreamRef.current?.getTracks().forEach((track) => track.stop());
    cameraStreamRef.current = null;
  }, []);

  // TanStack Virtual intentionally returns non-memoizable functions.
  // eslint-disable-next-line react-hooks/incompatible-library
  const rowVirtualizer = useVirtualizer({
    count: queue.length,
    getScrollElement: () => listParentRef.current,
    estimateSize: () => 360,
    overscan: 5
  });

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
        showToast(`Approved ${selectedItems.length} items`, 'success');
        setQueue(q => q.filter(i => !selectedItems.includes(i.id)));
        setSelectedItems([]);
      } else {
        showToast('Bulk approval failed', 'error');
      }
    } catch (e) {
      console.error('Bulk approve failed', e);
      showToast('Error during bulk approval', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async (item: Asset, service: string, overrides?: Record<string, unknown>) => {
    try {
      void overrides;
      const resp = await fetch(`/api/preview/${service}?item_id=${item.id}`);
      const data = await resp.json();
      
      setPreviewItem({ item, service, payload: data.payload });
    } catch (e) {
      console.error('Preview failed', e);
    }
  };

  const executeItem = async (item: Asset, services: string[], overrides?: Record<string, unknown>) => {
    try {
      showToast('Syncing to services...', 'info');
      const resp = await fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: item.id,
          service_names: services,
          overrides: overrides || item.user_overrides
        })
      });
      if (resp.ok) {
        showToast('Successfully synced!', 'success');
        setQueue(q => q.filter(i => i.id !== item.id));
        setPreviewItem(null);
      } else {
        showToast('Sync failed', 'error');
      }
    } catch (e) {
      console.error('Execution failed', e);
      showToast('Error executing sync', 'error');
    }
  };

  const uploadFiles = async (files: File[]) => {
    if (files.length === 0) return;

    setLoading(true);
    if (files.length > 1) {
      showToast(`Uploading ${files.length} images...`, 'info');
    }
    
    try {
      if (files.length === 1) {
        const sessionId = 'session-' + Date.now() + '-' + Math.random().toString(36).substring(2, 9);
        setProcessingFile(files[0]);
        setProcessingSessionId(sessionId);
        setProcessingLogs([]);
        setProcessingError(null);

        const formData = new FormData();
        formData.append('file', files[0]);
        formData.append('pipeline_id', selectedPipelineId);
        formData.append('settings', '{}');
        formData.append('session_id', sessionId);
        
        const resp = await fetch('/api/identify', {
          method: 'POST',
          body: formData,
        });
        if (resp.ok) {
          const resultData = await resp.json();
          
          if (resultData.item_id) {
            try {
              const itemResp = await fetch(`/api/items/${resultData.item_id}`);
              if (itemResp.ok) {
                const item = await itemResp.json();
                setLastIdentifyResult(item);
              }
            } catch (err) {
              console.error('Failed to fetch item details', err);
            }
          }
          await fetchQueue(queueStatus);
          
          // Clear processing state on success
          setProcessingFile(null);
          setProcessingSessionId(null);
        } else {
          showToast('Upload failed', 'error');
          setProcessingError('The pipeline failed to process the image. Please check logs or try another image.');
          setProcessingSessionId(null);
        }
      } else {
        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));
        formData.append('pipeline_id', selectedPipelineId);
        
        const resp = await fetch('/api/batch-upload', {
          method: 'POST',
          body: formData,
        });
        if (resp.ok) {
          showToast(`Batch of ${files.length} images uploaded!`, 'success');
          await fetchQueue(queueStatus);
        } else {
          showToast('Batch upload failed', 'error');
        }
      }
    } catch (e) {
      console.error('Upload failed', e);
      showToast('Error during upload', 'error');
      setProcessingError(e instanceof Error ? e.message : 'Error during upload');
      setProcessingSessionId(null);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    await uploadFiles(Array.from(files));
    event.target.value = '';
  };

  const closeCamera = () => {
    cameraStreamRef.current?.getTracks().forEach((track) => track.stop());
    cameraStreamRef.current = null;
    setCameraOpen(false);
    setCameraError('');
  };

  const openCamera = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      cameraInputRef.current?.click();
      return;
    }

    try {
      setCameraError('');
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
        audio: false,
      });
      cameraStreamRef.current = stream;
      setCameraOpen(true);
    } catch (error) {
      console.error('Camera access failed', error);
      setCameraError('Camera permission was denied or is unavailable. Falling back to file upload.');
      cameraInputRef.current?.click();
    }
  };

  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const capturePhoto = async () => {
    const video = cameraVideoRef.current;
    if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
      setCameraError('Camera preview is not ready yet.');
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext('2d');
    if (!context) {
      setCameraError('Unable to capture a frame from the camera.');
      return;
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92));
    if (!blob) {
      setCameraError('Unable to create an image from the camera feed.');
      return;
    }

    const file = new File([blob], `capture-${Date.now()}.jpg`, { type: 'image/jpeg' });
    closeCamera();
    await uploadFiles([file]);
  };

  const renderQueueCards = (showSelection: boolean) => {
    if (loading) {
      return (
        <div className="py-20 flex justify-center">
          <div className="w-8 h-8 border-2 border-white/10 border-t-white rounded-full animate-spin" />
        </div>
      );
    }

    if (queue.length === 0) {
      return (
        <div className="py-20 text-center glass rounded-[2rem]">
          <p className="text-white/30 text-sm font-medium">
            {queueStatus === 'approved' ? 'No approved assets yet.' : queueStatus === 'processing' ? 'No active batch items yet.' : 'Waiting for assets to ingest...'}
          </p>
        </div>
      );
    }

    return (
      <>
        {showSelection && queueStatus === 'pending' && (
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
        )}
        {showSelection && queueStatus === 'pending' && (
          <input
            type="checkbox"
            className="hidden"
            checked={selectedItems.length === queue.length}
            onChange={selectAll}
            id="selectAll"
          />
        )}
        <div ref={listParentRef} className="max-h-[72vh] overflow-y-auto pr-1">
          <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: 'relative' }}>
            {rowVirtualizer.getVirtualItems().map((virtualRow) => {
              const item = queue[virtualRow.index];
              return (
                <div
                  key={`${item.id}-${virtualRow.index}`}
                  ref={rowVirtualizer.measureElement}
                  data-index={virtualRow.index}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    transform: `translateY(${virtualRow.start}px)`
                  }}
                  className="pb-4"
                >
                  <AssetCard
                    item={item}
                    isSelected={showSelection ? selectedItems.includes(item.id) : false}
                    onToggleSelect={showSelection ? () => toggleSelection(item.id) : undefined}
                    onPreview={(svc, overrides) => handlePreview(item, svc, overrides)}
                    onExecute={(svcs, overrides) => executeItem(item, svcs, overrides)}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </>
    );
  };

  const getStageStatus = (stage: PipelineStageId) => {
    const hasLog = (text: string) => processingLogs.some(log => log.includes(text));

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

  const renderProcessingDashboard = () => {
    if (!processingFile) return null;

    const stages: Array<{ id: PipelineStageId; label: string; icon: string }> = [
      { id: 'barcode', label: 'Barcode Scanning', icon: '🔍' },
      { id: 'vision', label: 'Vision Identification', icon: '🤖' },
      { id: 'search', label: 'Web Enrichment', icon: '🌐' },
      { id: 'refine', label: 'Data Refinement', icon: '🧠' },
      { id: 'sync', label: 'Services Integration', icon: '🔌' }
    ];

    return (
      <div className="glass rounded-[2rem] p-6 sm:p-8 border border-white/10 animate-in fade-in duration-500 space-y-6">
        <div className="flex flex-col md:flex-row gap-8">
          {/* Left Pane: Image Preview with scanning line */}
          <div className="w-full md:w-1/3 flex flex-col items-center justify-center">
            <p className="label-apple mb-4">Ingested Image</p>
            <div className="relative w-full max-w-[280px] aspect-square rounded-2xl overflow-hidden bg-black/40 border border-white/10 shadow-inner">
              {processingFileUrl && (
                <img src={processingFileUrl} className="w-full h-full object-contain" alt="Processing preview" />
              )}
              {/* Laser Scan Line Animation */}
              {!processingError && (
                <div className="absolute left-0 w-full h-[3px] bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.8)] animate-scan" />
              )}
              {/* Pulsing overlay */}
              <div className="absolute inset-0 bg-cyan-500/5 animate-pulse mix-blend-overlay" />
            </div>
            {processingError ? (
              <button
                type="button"
                onClick={() => {
                  setProcessingFile(null);
                  setProcessingSessionId(null);
                  setProcessingError(null);
                }}
                className="mt-6 bg-red-600/20 hover:bg-red-600/30 text-red-200 border border-red-500/30 px-6 py-3 rounded-xl text-[10px] font-black tracking-widest uppercase transition-all"
              >
                Dismiss Error
              </button>
            ) : (
              <div className="mt-4 flex items-center gap-2 text-cyan-400/80 text-[10px] font-black tracking-widest uppercase animate-pulse">
                <span className="w-2 h-2 rounded-full bg-cyan-400" />
                Pipeline Processing...
              </div>
            )}
          </div>

          {/* Right Pane: Stages Tracker & Live Logs */}
          <div className="flex-1 flex flex-col space-y-6">
            <div>
              <p className="label-apple">Pipeline Stages</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {stages.map((stage) => {
                  const status = getStageStatus(stage.id);
                  return (
                    <div
                      key={stage.id}
                      className={`flex items-center gap-3 p-4 rounded-2xl border transition-all duration-300 ${
                        status === 'active' ? 'bg-cyan-950/20 border-cyan-500/40 shadow-[0_0_15px_rgba(6,182,212,0.05)]' :
                        status === 'completed' ? 'bg-green-950/10 border-green-500/20' :
                        'bg-white/5 border-white/5 opacity-50'
                      }`}
                    >
                      <span className="text-xl shrink-0">{stage.icon}</span>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-bold text-white leading-tight truncate">{stage.label}</p>
                        <p className={`text-[9px] font-black uppercase tracking-wider mt-1 ${
                          status === 'active' ? 'text-cyan-400 animate-pulse' :
                          status === 'completed' ? 'text-green-400' :
                          'text-white/30'
                        }`}>
                          {status === 'active' ? 'Processing' : status === 'completed' ? 'Completed' : 'Pending'}
                        </p>
                      </div>
                      <div className="shrink-0">
                        {status === 'active' ? (
                          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
                        ) : status === 'completed' ? (
                          <div className="w-2.5 h-2.5 rounded-full bg-green-500 flex items-center justify-center text-[7px] text-black font-black">✓</div>
                        ) : (
                          <div className="w-2.5 h-2.5 rounded-full bg-white/10" />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Console Logs */}
            <div className="flex-1 flex flex-col space-y-2 min-h-[180px]">
              <div className="flex justify-between items-center">
                <p className="label-apple">Real-Time Pipeline Logs</p>
                {processingSessionId && (
                  <span className="text-[9px] font-mono text-white/30 font-bold uppercase tracking-wider">ID: {processingSessionId}</span>
                )}
              </div>
              <div className="flex-1 bg-black/60 rounded-2xl border border-white/5 p-4 font-mono text-[11px] text-white/70 overflow-y-auto max-h-[220px] space-y-1.5 scrollbar-thin scrollbar-thumb-white/10 no-scrollbar">
                {processingLogs.length === 0 ? (
                  <p className="text-white/20 italic animate-pulse">Initializing pipeline session...</p>
                ) : (
                  processingLogs.map((log, index) => (
                    <div key={index} className="leading-relaxed border-l border-white/5 pl-2 hover:bg-white/5 transition-colors">
                      <span className="text-white/30 mr-2">[{index + 1}]</span>
                      <span className={log.includes('❌') || log.includes('⚠️') ? 'text-red-400' : log.includes('✨') || log.includes('🏁') ? 'text-green-400 font-semibold' : 'text-white/80'}>
                        {log}
                      </span>
                    </div>
                  ))
                )}
                {processingError && (
                  <div className="mt-2 p-2 bg-red-950/20 border border-red-500/30 rounded-lg text-red-300 font-bold">
                    ⚠️ Error: {processingError}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const selectedPipelineName = pipelines.find((pipeline) => pipeline.id === selectedPipelineId)?.name || DEFAULT_PIPELINE_OPTION.name;

  return (
    <div className="min-h-screen bg-black text-white selection:bg-blue-500/30 font-sans">
      <NetworkCheck />
      <Navbar activeTab={activeTab} setActiveTab={handleTabChange} />

      <main className="max-w-7xl mx-auto pt-32 px-6 pb-20">
        <div>
          <div className="space-y-8 max-w-6xl mx-auto">
            {activeTab === 'review' ? (
              <>
                <header className="flex justify-between items-end">
                  <div>
                    <h2 className="text-4xl font-extrabold tracking-tight mb-2">Review Queue</h2>
                    <p className="text-white/40 font-medium italic">Awaiting review and approved assets in one place.</p>
                  </div>
                  <button 
                    onClick={() => fetchQueue(queueStatus)} 
                    className="bg-white/5 hover:bg-white/10 px-4 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase"
                  >
                    Refresh Queue
                  </button>
                </header>

                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      setQueueStatus('all');
                      setSelectedItems([]);
                      void fetchQueue('all');
                    }}
                    className={`px-4 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase border transition-all ${
                      queueStatus === 'all' ? 'bg-white text-black border-white' : 'bg-white/5 text-white/60 border-white/10 hover:text-white'
                    }`}
                  >
                    Everything
                  </button>
                  <button
                    onClick={() => {
                      setQueueStatus('pending');
                      setSelectedItems([]);
                      void fetchQueue('pending');
                    }}
                    className={`px-4 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase border transition-all ${
                      queueStatus === 'pending' ? 'bg-white text-black border-white' : 'bg-white/5 text-white/60 border-white/10 hover:text-white'
                    }`}
                  >
                    Awaiting Review
                  </button>
                  <button
                    onClick={() => {
                      setQueueStatus('approved');
                      setSelectedItems([]);
                      void fetchQueue('approved');
                    }}
                    className={`px-4 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase border transition-all ${
                      queueStatus === 'approved' ? 'bg-white text-black border-white' : 'bg-white/5 text-white/60 border-white/10 hover:text-white'
                    }`}
                  >
                    Approved
                  </button>
                </div>

                <div className="space-y-4">
                  {renderQueueCards(queueStatus === 'pending')}
                </div>
              </>
            ) : activeTab === 'identify' ? (
              <div className="space-y-8">
                <header>
                  <h2 className="text-4xl font-extrabold tracking-tight mb-2">Identify Asset</h2>
                  <p className="text-white/40 font-medium italic">Capture or upload an image to begin AI processing.</p>
                </header>

                <div className="glass rounded-[2rem] p-6 border border-white/10 flex flex-col sm:flex-row sm:items-center gap-4 sm:justify-between">
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-[0.3em] text-white/40">Active Pipeline</p>
                    <p className="text-lg font-bold text-white mt-2">{selectedPipelineName}</p>
                  </div>
                  <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
                    <select
                      value={selectedPipelineId}
                      onChange={(event) => setSelectedPipelineId(event.target.value)}
                      className="bg-white/5 border border-white/10 rounded-2xl px-5 py-4 text-sm font-bold text-white focus:outline-none"
                    >
                      {(pipelines.length ? pipelines : [DEFAULT_PIPELINE_OPTION]).map((pipeline) => (
                        <option key={pipeline.id} value={pipeline.id} className="bg-black text-white">{pipeline.name}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => handleTabChange('pipelines')}
                      className="bg-white/5 hover:bg-white/10 px-4 py-4 rounded-2xl text-[10px] font-black tracking-widest uppercase"
                    >
                      Open Pipeline Editor
                    </button>
                  </div>
                </div>

                {processingFile ? (
                  renderProcessingDashboard()
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 animate-in fade-in duration-500">
                    <button
                      type="button"
                      onClick={() => void openCamera()}
                      className="glass rounded-[2rem] p-6 sm:p-8 flex items-center justify-center gap-4 border border-white/10 hover:border-blue-500/30 transition-all min-h-[120px] sm:min-h-0"
                    >
                      <div className="w-10 h-10 sm:w-12 sm:h-12 bg-blue-600 rounded-2xl flex items-center justify-center shadow-xl shadow-blue-500/40 shrink-0">
                        <Camera className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
                      </div>
                      <div className="text-left">
                        <p className="text-sm font-black uppercase tracking-widest">Open Camera</p>
                        <p className="text-[10px] text-white/50 leading-tight">Requests camera access or falls back to file upload</p>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => galleryInputRef.current?.click()}
                      className="glass rounded-[2rem] p-6 sm:p-8 flex items-center justify-center gap-4 border border-white/10 hover:border-blue-500/30 transition-all min-h-[120px] sm:min-h-0"
                    >
                      <div className="w-10 h-10 sm:w-12 sm:h-12 bg-white/10 rounded-2xl flex items-center justify-center shrink-0">
                        <Camera className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
                      </div>
                      <div className="text-left">
                        <p className="text-sm font-black uppercase tracking-widest">Upload Files</p>
                        <p className="text-[10px] text-white/50 leading-tight">Choose one or many images from gallery/files</p>
                      </div>
                    </button>

                    <input
                      ref={cameraInputRef}
                      type="file"
                      onChange={handleUpload}
                      className="hidden"
                      accept="image/*"
                      capture="environment"
                    />

                    <input
                      ref={galleryInputRef}
                      type="file"
                      onChange={handleUpload}
                      className="hidden"
                      accept="image/*"
                    />
                  </div>
                )}

                {lastIdentifyResult && (
                  <div className="space-y-6 pt-8 border-t border-white/5 animate-in fade-in slide-in-from-bottom-4 duration-1000">
                    <div className="flex items-center justify-between">
                      <h3 className="label-apple">Last Identification Result</h3>
                      <button 
                        onClick={() => setLastIdentifyResult(null)}
                        className="text-[10px] font-black uppercase tracking-widest text-white/20 hover:text-white/60 transition-colors"
                      >
                        Clear
                      </button>
                    </div>
                    <AssetCard
                      item={lastIdentifyResult}
                      isSelected={false}
                      onPreview={(svc, overrides) => handlePreview(lastIdentifyResult, svc, overrides)}
                      onExecute={(svcs, overrides) => executeItem(lastIdentifyResult, svcs, overrides)}
                    />
                    <p className="text-[10px] text-center text-white/20 font-medium">
                      This item is also available in the <button onClick={() => setActiveTab('review')} className="text-blue-500/50 hover:text-blue-500 transition-colors font-black uppercase">Review Queue</button>
                    </p>
                  </div>
                )}
              </div>
            ) : activeTab === 'batch' ? (
              <div className="space-y-8">
                <header className="flex justify-between items-end">
                  <div>
                    <h2 className="text-4xl font-extrabold tracking-tight mb-2">Batch Mode</h2>
                    <p className="text-white/40 font-medium italic">Set up large ingestions and monitor active processing.</p>
                  </div>
                  <button
                    onClick={() => fetchQueue(queueStatus)}
                    className="bg-white/5 hover:bg-white/10 px-4 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase"
                  >
                    Refresh Queue
                  </button>
                </header>

                <div className="glass rounded-[2rem] p-6 border border-white/10 flex flex-col sm:flex-row sm:items-center gap-4 sm:justify-between">
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-[0.3em] text-white/40">Batch Pipeline</p>
                    <p className="text-lg font-bold text-white mt-2">{selectedPipelineName}</p>
                  </div>
                  <select
                    value={selectedPipelineId}
                    onChange={(event) => setSelectedPipelineId(event.target.value)}
                    className="bg-white/5 border border-white/10 rounded-2xl px-5 py-4 text-sm font-bold text-white focus:outline-none"
                  >
                    {(pipelines.length ? pipelines : [DEFAULT_PIPELINE_OPTION]).map((pipeline) => (
                      <option key={pipeline.id} value={pipeline.id} className="bg-black text-white">{pipeline.name}</option>
                    ))}
                  </select>
                </div>

                <div className="glass rounded-[2rem] p-8 border border-white/10 space-y-6">
                  <div className="flex items-center justify-between">
                    <h3 className="label-apple">Batch Upload</h3>
                  </div>
                  <button
                    type="button"
                    onClick={() => batchInputRef.current?.click()}
                    className="w-full py-10 rounded-[2rem] border-2 border-dashed border-white/10 hover:border-blue-500/30 text-xs font-black uppercase tracking-[0.3em] text-white/40 hover:text-white transition-all"
                  >
                    Select Multiple Images
                  </button>
                  <input
                    ref={batchInputRef}
                    type="file"
                    onChange={handleUpload}
                    className="hidden"
                    accept="image/*"
                    multiple
                  />
                </div>

                <div className="space-y-4">
                  {renderQueueCards(false)}
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
        </div>
      </main>

      {cameraOpen && (
        <div className="fixed inset-0 z-[1400] bg-black/90 backdrop-blur-xl flex items-center justify-center p-6">
          <div className="glass w-full max-w-3xl rounded-[3rem] p-6 space-y-6 border border-white/10">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-2xl font-black tracking-tight">Camera Capture</h3>
                <p className="text-sm text-white/40">Take a photo and send it through the selected pipeline.</p>
              </div>
              <button onClick={closeCamera} className="w-12 h-12 rounded-2xl bg-white/5 text-xl">✕</button>
            </div>

            <div className="bg-black rounded-[2rem] overflow-hidden border border-white/10">
              <video ref={cameraVideoRef} className="w-full max-h-[60vh] object-cover" playsInline muted autoPlay />
            </div>

            {cameraError && <p className="text-sm text-red-300">{cameraError}</p>}

            <div className="flex gap-3 justify-end">
              <button onClick={closeCamera} className="px-5 py-3 rounded-2xl bg-white/5 text-[10px] font-black uppercase tracking-widest">Cancel</button>
              <button onClick={() => void capturePhoto()} className="btn-apple px-6 py-3 rounded-2xl text-[10px] font-black uppercase tracking-widest">Capture and Process</button>
            </div>
          </div>
        </div>
      )}

      {previewItem && (
        <PreviewModal 
          preview={previewItem} 
          onClose={() => setPreviewItem(null)} 
          onConfirm={(overrides) => executeItem(previewItem.item, [previewItem.service], overrides)}
        />
      )}

      {/* Toast Notifications */}
      {toast && (
        <div className="fixed bottom-32 left-1/2 -translate-x-1/2 z-[2000] animate-in fade-in slide-in-from-bottom-4 duration-300">
          <div className={`px-8 py-4 rounded-[2rem] shadow-2xl flex items-center gap-4 border backdrop-blur-3xl ${
            toast.type === 'error' ? 'bg-red-500/20 border-red-500/50 text-red-200' : 
            toast.type === 'success' ? 'bg-green-500/20 border-green-500/50 text-green-200' :
            'bg-blue-500/20 border-blue-500/50 text-blue-100'
          }`}>
            <span className="text-sm font-black uppercase tracking-widest">{toast.message}</span>
          </div>
        </div>
      )}
    </div>
  );
}


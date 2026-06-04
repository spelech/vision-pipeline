import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { Asset } from './types';
import { Navbar } from './components/Navbar';
import { PreviewModal } from './components/PreviewModal';
import { Settings } from './components/Settings';
import { NetworkCheck } from './components/NetworkCheck';

import { PipelineEditor } from './components/PipelineEditor';
import { ReviewTab } from './app/ReviewTab';
import { IdentifyTab } from './app/IdentifyTab';
import { BatchTab } from './app/BatchTab';
import { ReceiptsTab } from './app/ReceiptsTab';
import { CameraCaptureModal } from './app/CameraCaptureModal';
import { ToastBanner } from './app/ToastBanner';
import type { ActiveTab, PipelineSummary, QueueStatus, ToastState, ToastType } from './app/types';

const DEFAULT_PIPELINE_OPTION: PipelineSummary = { id: 'default', name: 'Default Vision Pipeline' };

export default function App() {
  const [queue, setQueue] = useState<Asset[]>([]);
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>('identify');
  const [queueStatus, setQueueStatus] = useState<QueueStatus>('all');
  const [previewItem, setPreviewItem] = useState<{item: Asset, service: string, payload: Record<string, unknown>} | null>(null);
  const [pipelines, setPipelines] = useState<PipelineSummary[]>([]);
  const [selectedPipelineId, setSelectedPipelineId] = useState('default');
  const [searchResultsLimit, setSearchResultsLimit] = useState(7);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [lastIdentifyResult, setLastIdentifyResult] = useState<Asset | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [helperText, setHelperText] = useState('');
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

  const fetchQueue = useCallback(async (status: QueueStatus = 'all') => {
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

  const handleTabChange = (tab: ActiveTab) => {
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

  const deleteItem = async (item: Asset) => {
    try {
      const resp = await fetch(`/api/items/${item.id}`, {
        method: 'DELETE',
      });

      if (!resp.ok) {
        showToast('Delete failed', 'error');
        return;
      }

      setQueue((current) => current.filter((queuedItem) => queuedItem.id !== item.id));
      setSelectedItems((current) => current.filter((selectedItemId) => selectedItemId !== item.id));
      setPreviewItem((current) => (current?.item.id === item.id ? null : current));
      showToast('Deleted item', 'success');
    } catch (e) {
      console.error('Delete failed', e);
      showToast('Delete failed', 'error');
    }
  };

  const uploadFiles = async (files: File[], text?: string) => {
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
        formData.append('settings', JSON.stringify({ search_results_limit: searchResultsLimit }));
        formData.append('session_id', sessionId);
        if (text) {
          formData.append('text', text);
        }
        
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
          setHelperText('');
        } else {
          showToast('Upload failed', 'error');
          setProcessingError('The pipeline failed to process the image. Please check logs or try another image.');
          setProcessingSessionId(null);
        }
      } else {
        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));
        formData.append('pipeline_id', selectedPipelineId);
        formData.append('settings', JSON.stringify({ search_results_limit: searchResultsLimit }));
        if (text) {
          formData.append('text', text);
        }
        
        const resp = await fetch('/api/batch-upload', {
          method: 'POST',
          body: formData,
        });
        if (resp.ok) {
          showToast(`Batch of ${files.length} images uploaded!`, 'success');
          setHelperText('');
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

    await uploadFiles(Array.from(files), helperText);
    event.target.value = '';
  };

  const closeCamera = () => {
    cameraStreamRef.current?.getTracks().forEach((track) => track.stop());
    cameraStreamRef.current = null;
    setCameraOpen(false);
    setCameraError('');
  };

  useEffect(() => {
    return () => {
      if (toastTimeoutRef.current) {
        clearTimeout(toastTimeoutRef.current);
      }
    };
  }, []);

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

  const toastTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (message: string, type: ToastType = 'info') => {
    if (toastTimeoutRef.current) {
      clearTimeout(toastTimeoutRef.current);
    }
    setToast({ message, type });
    toastTimeoutRef.current = setTimeout(() => {
      setToast(null);
      toastTimeoutRef.current = null;
    }, 4000);
  };

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const sharedBatchId = params.get('shared_batch_id');
      if (sharedBatchId) {
        setActiveTab('batch');
        setQueueStatus('processing');
        const newUrl = window.location.pathname;
        window.history.replaceState({}, '', newUrl);
        showToast('Shared batch loaded for review!', 'success');
      }
    }
  }, []);


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
    await uploadFiles([file], helperText);
  };

  const selectedPipelineName = pipelines.find((pipeline) => pipeline.id === selectedPipelineId)?.name || DEFAULT_PIPELINE_OPTION.name;

  return (
    <div className="min-h-screen bg-black text-white selection:bg-blue-500/30 font-sans compact-desktop">
      <NetworkCheck />
      <Navbar activeTab={activeTab} setActiveTab={handleTabChange} />

      <main className="max-w-7xl mx-auto pt-32 px-6 pb-20">
        <div>
          <div className="space-y-8 max-w-6xl mx-auto">
            {activeTab === 'review' ? (
              <ReviewTab
                queue={queue}
                selectedItems={selectedItems}
                loading={loading}
                queueStatus={queueStatus}
                rowVirtualizer={rowVirtualizer}
                listParentRef={listParentRef}
                onRefreshQueue={() => void fetchQueue(queueStatus)}
                onSetQueueStatus={setQueueStatus}
                onClearSelectedItems={() => setSelectedItems([])}
                onSelectAll={selectAll}
                onToggleSelection={toggleSelection}
                onBulkApprove={() => void handleBulkApprove()}
                onDelete={deleteItem}
                onPreview={handlePreview}
                onExecute={executeItem}
                onFetchQueue={(status) => void fetchQueue(status)}
              />
            ) : activeTab === 'identify' ? (
              <IdentifyTab
                pipelines={pipelines}
                selectedPipelineId={selectedPipelineId}
                selectedPipelineName={selectedPipelineName}
                searchResultsLimit={searchResultsLimit}
                defaultPipelineOption={DEFAULT_PIPELINE_OPTION}
                processingFile={processingFile}
                processingFileUrl={processingFileUrl}
                processingSessionId={processingSessionId}
                processingLogs={processingLogs}
                processingError={processingError}
                lastIdentifyResult={lastIdentifyResult}
                helperText={helperText}
                onSetHelperText={setHelperText}
                cameraInputRef={cameraInputRef}
                galleryInputRef={galleryInputRef}
                onSetSelectedPipelineId={setSelectedPipelineId}
                onSetSearchResultsLimit={setSearchResultsLimit}
                onOpenPipelineEditor={() => handleTabChange('pipelines')}
                onOpenCamera={() => void openCamera()}
                onHandleUpload={(event) => {
                  void handleUpload(event);
                }}
                onDismissProcessingError={() => {
                  setProcessingFile(null);
                  setProcessingSessionId(null);
                  setProcessingError(null);
                }}
                onClearLastIdentifyResult={() => setLastIdentifyResult(null)}
                onOpenReviewTab={() => setActiveTab('review')}
                onPreview={handlePreview}
                onExecute={executeItem}
              />
            ) : activeTab === 'batch' ? (
              <BatchTab
                queue={queue}
                selectedItems={selectedItems}
                loading={loading}
                queueStatus={queueStatus}
                selectedPipelineId={selectedPipelineId}
                selectedPipelineName={selectedPipelineName}
                searchResultsLimit={searchResultsLimit}
                pipelines={pipelines}
                defaultPipelineOption={DEFAULT_PIPELINE_OPTION}
                rowVirtualizer={rowVirtualizer}
                listParentRef={listParentRef}
                batchInputRef={batchInputRef}
                onRefreshQueue={() => void fetchQueue(queueStatus)}
                onSetSelectedPipelineId={setSelectedPipelineId}
                onSetSearchResultsLimit={setSearchResultsLimit}
                onHandleUpload={(event) => {
                  void handleUpload(event);
                }}
                onSelectAll={selectAll}
                onToggleSelection={toggleSelection}
                onBulkApprove={() => void handleBulkApprove()}
                onPreview={handlePreview}
                onExecute={executeItem}
              />
            ) : activeTab === 'receipts' ? (
              <ReceiptsTab onToast={showToast} />
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

      <CameraCaptureModal
        cameraOpen={cameraOpen}
        cameraError={cameraError}
        cameraVideoRef={cameraVideoRef}
        onClose={closeCamera}
        onCapture={() => {
          void capturePhoto();
        }}
      />

      {previewItem && (
        <PreviewModal 
          preview={previewItem} 
          onClose={() => setPreviewItem(null)} 
          onConfirm={(overrides) => executeItem(previewItem.item, [previewItem.service], overrides)}
        />
      )}

      <ToastBanner toast={toast} />
    </div>
  );
}


import type React from 'react';
import { Camera } from 'lucide-react';

import type { Asset } from '../types';
import { AssetCard } from '../components/AssetCard';
import { ProcessingDashboard } from './ProcessingDashboard';
import type { PipelineSummary } from './types';

interface IdentifyTabProps {
  pipelines: PipelineSummary[];
  selectedPipelineId: string;
  selectedPipelineName: string;
  searchResultsLimit: number;
  defaultPipelineOption: PipelineSummary;
  processingFile: File | null;
  processingFileUrl: string;
  processingSessionId: string | null;
  processingLogs: string[];
  processingError: string | null;
  lastIdentifyResult: Asset | null;
  cameraInputRef: React.RefObject<HTMLInputElement | null>;
  galleryInputRef: React.RefObject<HTMLInputElement | null>;
  onSetSelectedPipelineId: (pipelineId: string) => void;
  onSetSearchResultsLimit: (value: number) => void;
  onOpenPipelineEditor: () => void;
  onOpenCamera: () => void;
  onHandleUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onDismissProcessingError: () => void;
  onClearLastIdentifyResult: () => void;
  onOpenReviewTab: () => void;
  onPreview: (item: Asset, service: string, overrides?: Record<string, unknown>) => void;
  onExecute: (item: Asset, services: string[], overrides?: Record<string, unknown>) => void;
}

export function IdentifyTab({
  pipelines,
  selectedPipelineId,
  selectedPipelineName,
  searchResultsLimit,
  defaultPipelineOption,
  processingFile,
  processingFileUrl,
  processingSessionId,
  processingLogs,
  processingError,
  lastIdentifyResult,
  cameraInputRef,
  galleryInputRef,
  onSetSelectedPipelineId,
  onSetSearchResultsLimit,
  onOpenPipelineEditor,
  onOpenCamera,
  onHandleUpload,
  onDismissProcessingError,
  onClearLastIdentifyResult,
  onOpenReviewTab,
  onPreview,
  onExecute,
}: IdentifyTabProps) {
  return (
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
            onChange={(event) => onSetSelectedPipelineId(event.target.value)}
            className="bg-white/5 border border-white/10 rounded-2xl px-5 py-4 text-sm font-bold text-white focus:outline-none"
          >
            {(pipelines.length ? pipelines : [defaultPipelineOption]).map((pipeline) => (
              <option key={pipeline.id} value={pipeline.id} className="bg-black text-white">
                {pipeline.name}
              </option>
            ))}
          </select>
          <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-3 py-2">
            <label className="text-[9px] font-black uppercase tracking-widest text-white/50">Search Results</label>
            <input
              type="number"
              min={1}
              max={50}
              value={searchResultsLimit}
              onChange={(event) => onSetSearchResultsLimit(Number(event.target.value) || 7)}
              className="w-16 rounded-xl bg-black/30 px-2 py-1 text-sm font-bold text-white focus:outline-none"
            />
          </div>
          <button
            type="button"
            onClick={onOpenPipelineEditor}
            className="bg-white/5 hover:bg-white/10 px-4 py-4 rounded-2xl text-[10px] font-black tracking-widest uppercase"
          >
            Open Pipeline Editor
          </button>
        </div>
      </div>

      {processingFile ? (
        <ProcessingDashboard
          processingFile={processingFile}
          processingFileUrl={processingFileUrl}
          processingSessionId={processingSessionId}
          processingLogs={processingLogs}
          processingError={processingError}
          onDismissError={onDismissProcessingError}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 animate-in fade-in duration-500">
          <button
            type="button"
            onClick={onOpenCamera}
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
            onChange={onHandleUpload}
            className="hidden"
            accept="image/*"
            capture="environment"
          />

          <input ref={galleryInputRef} type="file" onChange={onHandleUpload} className="hidden" accept="image/*" />
        </div>
      )}

      {lastIdentifyResult && (
        <div className="space-y-6 pt-8 border-t border-white/5 animate-in fade-in slide-in-from-bottom-4 duration-1000">
          <div className="flex items-center justify-between">
            <h3 className="label-apple">Last Identification Result</h3>
            <button
              onClick={onClearLastIdentifyResult}
              className="text-[10px] font-black uppercase tracking-widest text-white/20 hover:text-white/60 transition-colors"
            >
              Clear
            </button>
          </div>
          <AssetCard
            item={lastIdentifyResult}
            isSelected={false}
            onPreview={(svc, overrides) => onPreview(lastIdentifyResult, svc, overrides)}
            onExecute={(svcs, overrides) => onExecute(lastIdentifyResult, svcs, overrides)}
          />
          <p className="text-[10px] text-center text-white/20 font-medium">
            This item is also available in the{' '}
            <button onClick={onOpenReviewTab} className="text-blue-500/50 hover:text-blue-500 transition-colors font-black uppercase">
              Review Queue
            </button>
          </p>
        </div>
      )}
    </div>
  );
}

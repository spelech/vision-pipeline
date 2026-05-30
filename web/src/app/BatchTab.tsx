import type React from 'react';
import type { Virtualizer } from '@tanstack/react-virtual';

import { QueueCards } from './QueueCards';
import type { PipelineSummary, QueueStatus } from './types';
import type { Asset } from '../types';

interface BatchTabProps {
  queue: Asset[];
  selectedItems: string[];
  loading: boolean;
  queueStatus: QueueStatus;
  selectedPipelineId: string;
  selectedPipelineName: string;
  searchResultsLimit: number;
  pipelines: PipelineSummary[];
  defaultPipelineOption: PipelineSummary;
  rowVirtualizer: Virtualizer<HTMLDivElement, Element>;
  listParentRef: React.RefObject<HTMLDivElement | null>;
  batchInputRef: React.RefObject<HTMLInputElement | null>;
  onRefreshQueue: () => void;
  onSetSelectedPipelineId: (pipelineId: string) => void;
  onSetSearchResultsLimit: (value: number) => void;
  onHandleUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onSelectAll: () => void;
  onToggleSelection: (id: string) => void;
  onBulkApprove: () => void;
  onPreview: (item: Asset, service: string, overrides?: Record<string, unknown>) => void;
  onExecute: (item: Asset, services: string[], overrides?: Record<string, unknown>) => void;
}

export function BatchTab({
  queue,
  selectedItems,
  loading,
  queueStatus,
  selectedPipelineId,
  selectedPipelineName,
  searchResultsLimit,
  pipelines,
  defaultPipelineOption,
  rowVirtualizer,
  listParentRef,
  batchInputRef,
  onRefreshQueue,
  onSetSelectedPipelineId,
  onSetSearchResultsLimit,
  onHandleUpload,
  onSelectAll,
  onToggleSelection,
  onBulkApprove,
  onPreview,
  onExecute,
}: BatchTabProps) {
  return (
    <div className="space-y-8">
      <header className="flex justify-between items-end">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight mb-2">Batch Mode</h2>
          <p className="text-white/40 font-medium italic">Set up large ingestions and monitor active processing.</p>
        </div>
        <button
          onClick={onRefreshQueue}
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
        <div className="flex items-center gap-3">
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
        </div>
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
        <input ref={batchInputRef} type="file" onChange={onHandleUpload} className="hidden" accept="image/*" multiple />
      </div>

      <div className="space-y-4">
        <QueueCards
          loading={loading}
          queue={queue}
          queueStatus={queueStatus}
          showSelection={false}
          selectedItems={selectedItems}
          rowVirtualizer={rowVirtualizer}
          listParentRef={listParentRef}
          onSelectAll={onSelectAll}
          onToggleSelection={onToggleSelection}
          onBulkApprove={onBulkApprove}
          onPreview={onPreview}
          onExecute={onExecute}
        />
      </div>
    </div>
  );
}

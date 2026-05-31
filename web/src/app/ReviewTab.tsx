import type React from 'react';
import type { Virtualizer } from '@tanstack/react-virtual';

import type { Asset } from '../types';
import { QueueCards } from './QueueCards';
import type { QueueStatus } from './types';

interface ReviewTabProps {
  queue: Asset[];
  selectedItems: string[];
  loading: boolean;
  queueStatus: QueueStatus;
  rowVirtualizer: Virtualizer<HTMLDivElement, Element>;
  listParentRef: React.RefObject<HTMLDivElement | null>;
  onRefreshQueue: () => void;
  onSetQueueStatus: (status: QueueStatus) => void;
  onClearSelectedItems: () => void;
  onSelectAll: () => void;
  onToggleSelection: (id: string) => void;
  onBulkApprove: () => void;
  onDelete?: (item: Asset) => void;
  onPreview: (item: Asset, service: string, overrides?: Record<string, unknown>) => void;
  onExecute: (item: Asset, services: string[], overrides?: Record<string, unknown>) => void;
  onFetchQueue: (status: QueueStatus) => void;
}

export function ReviewTab({
  queue,
  selectedItems,
  loading,
  queueStatus,
  rowVirtualizer,
  listParentRef,
  onRefreshQueue,
  onSetQueueStatus,
  onClearSelectedItems,
  onSelectAll,
  onToggleSelection,
  onBulkApprove,
  onDelete,
  onPreview,
  onExecute,
  onFetchQueue,
}: ReviewTabProps) {
  return (
    <>
      <header className="flex justify-between items-end">
        <div>
          <h2 className="text-4xl font-extrabold tracking-tight mb-2">Review Queue</h2>
          <p className="text-white/40 font-medium italic">Awaiting review and approved assets in one place.</p>
        </div>
        <button
          onClick={onRefreshQueue}
          className="bg-white/5 hover:bg-white/10 px-4 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase"
        >
          Refresh Queue
        </button>
      </header>

      <div className="flex gap-2">
        <button
          onClick={() => {
            onSetQueueStatus('all');
            onClearSelectedItems();
            onFetchQueue('all');
          }}
          className={`px-4 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase border transition-all ${
            queueStatus === 'all' ? 'bg-white text-black border-white' : 'bg-white/5 text-white/60 border-white/10 hover:text-white'
          }`}
        >
          Everything
        </button>
        <button
          onClick={() => {
            onSetQueueStatus('pending');
            onClearSelectedItems();
            onFetchQueue('pending');
          }}
          className={`px-4 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase border transition-all ${
            queueStatus === 'pending' ? 'bg-white text-black border-white' : 'bg-white/5 text-white/60 border-white/10 hover:text-white'
          }`}
        >
          Awaiting Review
        </button>
        <button
          onClick={() => {
            onSetQueueStatus('approved');
            onClearSelectedItems();
            onFetchQueue('approved');
          }}
          className={`px-4 py-2 rounded-xl text-[10px] font-black tracking-widest uppercase border transition-all ${
            queueStatus === 'approved' ? 'bg-white text-black border-white' : 'bg-white/5 text-white/60 border-white/10 hover:text-white'
          }`}
        >
          Approved
        </button>
      </div>

      <div className="space-y-4">
        <QueueCards
          loading={loading}
          queue={queue}
          queueStatus={queueStatus}
          showSelection={queueStatus === 'pending'}
          selectedItems={selectedItems}
          rowVirtualizer={rowVirtualizer}
          listParentRef={listParentRef}
          onSelectAll={onSelectAll}
          onToggleSelection={onToggleSelection}
          onBulkApprove={onBulkApprove}
          onDelete={onDelete}
          onPreview={onPreview}
          onExecute={onExecute}
        />
      </div>
    </>
  );
}

import type React from 'react';
import type { Virtualizer } from '@tanstack/react-virtual';

import type { Asset } from '../types';
import { AssetCard } from '../components/AssetCard';
import type { QueueStatus } from './types';

interface QueueCardsProps {
  loading: boolean;
  queue: Asset[];
  queueStatus: QueueStatus;
  showSelection: boolean;
  selectedItems: string[];
  rowVirtualizer: Virtualizer<HTMLDivElement, Element>;
  listParentRef: React.RefObject<HTMLDivElement | null>;
  onSelectAll: () => void;
  onToggleSelection: (id: string) => void;
  onBulkApprove: () => void;
  onDelete?: (item: Asset) => void;
  onPreview: (item: Asset, service: string, overrides?: Record<string, unknown>) => void;
  onExecute: (item: Asset, services: string[], overrides?: Record<string, unknown>) => void;
}

export function QueueCards({
  loading,
  queue,
  queueStatus,
  showSelection,
  selectedItems,
  rowVirtualizer,
  listParentRef,
  onSelectAll,
  onToggleSelection,
  onBulkApprove,
  onDelete,
  onPreview,
  onExecute,
}: QueueCardsProps) {
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
          {queueStatus === 'approved'
            ? 'No approved assets yet.'
            : queueStatus === 'processing'
              ? 'No active batch items yet.'
              : 'Waiting for assets to ingest...'}
        </p>
      </div>
    );
  }

  return (
    <>
      {showSelection && queueStatus === 'pending' && (
        <div className="flex justify-between items-center px-4">
          <label htmlFor="selectAll" className="flex items-center gap-3 cursor-pointer group">
            <div
              className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                selectedItems.length === queue.length
                  ? 'bg-blue-500 border-blue-500'
                  : 'border-white/30 group-hover:border-white/50'
              }`}
            >
              {selectedItems.length === queue.length && <div className="w-2.5 h-2.5 bg-white rounded-[2px]" />}
            </div>
            <span className="text-sm font-bold text-white/70 group-hover:text-white transition-colors">Select All</span>
          </label>
          {selectedItems.length > 0 && (
            <button
              onClick={onBulkApprove}
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
          onChange={onSelectAll}
          id="selectAll"
        />
      )}
      <div ref={listParentRef} className="max-h-[72vh] overflow-y-auto pr-1">
        <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: 'relative' }}>
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const item = queue[virtualRow.index];
            if (!item) return null;

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
                  transform: `translateY(${virtualRow.start}px)`,
                }}
                className="pb-4"
              >
                <AssetCard
                  item={item}
                  isSelected={showSelection ? selectedItems.includes(item.id) : false}
                  onToggleSelect={showSelection ? () => onToggleSelection(item.id) : undefined}
                  onDelete={onDelete ? () => onDelete(item) : undefined}
                  onPreview={(svc, overrides) => onPreview(item, svc, overrides)}
                  onExecute={(svcs, overrides) => onExecute(item, svcs, overrides)}
                />
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

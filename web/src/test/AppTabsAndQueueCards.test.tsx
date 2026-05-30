import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { Asset } from '../types';
import { QueueCards } from '../app/QueueCards';
import { BatchTab } from '../app/BatchTab';
import { IdentifyTab } from '../app/IdentifyTab';
import { ReviewTab } from '../app/ReviewTab';
import type { PipelineSummary } from '../app/types';

vi.mock('../components/AssetCard', () => ({
  AssetCard: ({
    item,
    onToggleSelect,
    onPreview,
    onExecute,
  }: {
    item: Asset;
    onToggleSelect?: () => void;
    onPreview: (service: string, overrides: Record<string, unknown>) => void;
    onExecute: (services: string[], overrides: Record<string, unknown>) => void;
  }) => (
    <div data-testid={`asset-${item.id}`}>
      {item.id}
      <button data-testid={`toggle-${item.id}`} onClick={() => onToggleSelect?.()}>
        toggle
      </button>
      <button data-testid={`preview-${item.id}`} onClick={() => onPreview('homebox', { sample: true })}>
        preview
      </button>
      <button data-testid={`execute-${item.id}`} onClick={() => onExecute(['homebox'], { sample: true })}>
        execute
      </button>
    </div>
  ),
}));

vi.mock('../app/ProcessingDashboard', () => ({
  ProcessingDashboard: () => <div data-testid="processing-dashboard">processing</div>,
}));

const baseAsset: Asset = {
  id: 'a1',
  image_path: 'img.jpg',
  status: 'pending',
  product_type: 'product',
  selected_services: ['homebox'],
  ai_output: { llm_output: { product_name: 'Widget' } },
};

const defaultPipeline: PipelineSummary = { id: 'default', name: 'Default' };

const virtualizer = {
  getTotalSize: () => 120,
  getVirtualItems: () => [{ index: 0, start: 0 }],
  measureElement: vi.fn(),
};

describe('QueueCards', () => {
  it('Feature: queue-cards-loading | renders spinner while loading', () => {
    render(
      <QueueCards
        loading
        queue={[]}
        queueStatus="all"
        showSelection={false}
        selectedItems={[]}
        rowVirtualizer={virtualizer as never}
        listParentRef={{ current: null }}
        onSelectAll={vi.fn()}
        onToggleSelection={vi.fn()}
        onBulkApprove={vi.fn()}
        onPreview={vi.fn()}
        onExecute={vi.fn()}
      />,
    );

    expect(document.querySelector('.animate-spin')).toBeTruthy();
  });

  it('Feature: queue-cards-empty-states | renders status-specific empty messages', () => {
    const { rerender } = render(
      <QueueCards
        loading={false}
        queue={[]}
        queueStatus="approved"
        showSelection={false}
        selectedItems={[]}
        rowVirtualizer={virtualizer as never}
        listParentRef={{ current: null }}
        onSelectAll={vi.fn()}
        onToggleSelection={vi.fn()}
        onBulkApprove={vi.fn()}
        onPreview={vi.fn()}
        onExecute={vi.fn()}
      />,
    );
    expect(screen.getByText(/No approved assets yet/i)).toBeInTheDocument();

    rerender(
      <QueueCards
        loading={false}
        queue={[]}
        queueStatus="processing"
        showSelection={false}
        selectedItems={[]}
        rowVirtualizer={virtualizer as never}
        listParentRef={{ current: null }}
        onSelectAll={vi.fn()}
        onToggleSelection={vi.fn()}
        onBulkApprove={vi.fn()}
        onPreview={vi.fn()}
        onExecute={vi.fn()}
      />,
    );
    expect(screen.getByText(/No active batch items yet/i)).toBeInTheDocument();
  });

  it('Feature: queue-cards-selection-controls | toggles select-all and bulk approval controls', () => {
    const onSelectAll = vi.fn();
    const onBulkApprove = vi.fn();

    render(
      <QueueCards
        loading={false}
        queue={[baseAsset]}
        queueStatus="pending"
        showSelection
        selectedItems={[baseAsset.id]}
        rowVirtualizer={virtualizer as never}
        listParentRef={{ current: null }}
        onSelectAll={onSelectAll}
        onToggleSelection={vi.fn()}
        onBulkApprove={onBulkApprove}
        onPreview={vi.fn()}
        onExecute={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText(/Select All/i));
    fireEvent.click(screen.getByText(/Approve 1 Items/i));

    expect(onSelectAll).toHaveBeenCalled();
    expect(onBulkApprove).toHaveBeenCalled();
    expect(screen.getByTestId('asset-a1')).toBeInTheDocument();
  });

  it('Feature: queue-cards-callback-wrappers | forwards toggle preview execute events through item-bound handlers', () => {
    const onToggleSelection = vi.fn();
    const onPreview = vi.fn();
    const onExecute = vi.fn();

    render(
      <QueueCards
        loading={false}
        queue={[baseAsset]}
        queueStatus="pending"
        showSelection
        selectedItems={[]}
        rowVirtualizer={virtualizer as never}
        listParentRef={{ current: null }}
        onSelectAll={vi.fn()}
        onToggleSelection={onToggleSelection}
        onBulkApprove={vi.fn()}
        onPreview={onPreview}
        onExecute={onExecute}
      />,
    );

    fireEvent.click(screen.getByTestId('toggle-a1'));
    fireEvent.click(screen.getByTestId('preview-a1'));
    fireEvent.click(screen.getByTestId('execute-a1'));

    expect(onToggleSelection).toHaveBeenCalledWith('a1');
    expect(onPreview).toHaveBeenCalledWith(baseAsset, 'homebox', { sample: true });
    expect(onExecute).toHaveBeenCalledWith(baseAsset, ['homebox'], { sample: true });
  });
});

describe('App tab wrappers', () => {
  it('Feature: batch-tab-wrapper | renders controls and delegates queue rendering', () => {
    const onRefreshQueue = vi.fn();
    const onPipelineChange = vi.fn();
    const onHandleUpload = vi.fn();
    const uploadRef = { current: { click: vi.fn() } as unknown as HTMLInputElement };

    const { container } = render(
      <BatchTab
        queue={[baseAsset]}
        selectedItems={[]}
        loading={false}
        queueStatus="processing"
        selectedPipelineId="default"
        selectedPipelineName="Default"
        pipelines={[defaultPipeline]}
        defaultPipelineOption={defaultPipeline}
        rowVirtualizer={virtualizer as never}
        listParentRef={{ current: null }}
        batchInputRef={uploadRef}
        onRefreshQueue={onRefreshQueue}
        onSetSelectedPipelineId={onPipelineChange}
        onHandleUpload={onHandleUpload}
        onSelectAll={vi.fn()}
        onToggleSelection={vi.fn()}
        onBulkApprove={vi.fn()}
        onPreview={vi.fn()}
        onExecute={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText(/Refresh Queue/i));
    fireEvent.change(screen.getByDisplayValue('Default'), { target: { value: 'default' } });
    const batchInput = container.querySelector('input[type="file"][multiple]') as HTMLInputElement;
    fireEvent.change(batchInput, {
      target: { files: [new File(['1'], 'batch.jpg', { type: 'image/jpeg' })] },
    });

    expect(onRefreshQueue).toHaveBeenCalled();
    expect(onPipelineChange).toHaveBeenCalled();
    expect(onHandleUpload).toHaveBeenCalled();
    expect(screen.getByTestId('asset-a1')).toBeInTheDocument();
  });

  it('Feature: identify-tab-wrapper | renders camera/upload state and processing dashboard branches', () => {
    const onOpenCamera = vi.fn();
    const onOpenEditor = vi.fn();

    const { rerender } = render(
      <IdentifyTab
        pipelines={[defaultPipeline]}
        selectedPipelineId="default"
        selectedPipelineName="Default"
        defaultPipelineOption={defaultPipeline}
        processingFile={null}
        processingFileUrl=""
        processingSessionId={null}
        processingLogs={[]}
        processingError={null}
        lastIdentifyResult={baseAsset}
        cameraInputRef={{ current: null }}
        galleryInputRef={{ current: null }}
        onSetSelectedPipelineId={vi.fn()}
        onOpenPipelineEditor={onOpenEditor}
        onOpenCamera={onOpenCamera}
        onHandleUpload={vi.fn()}
        onDismissProcessingError={vi.fn()}
        onClearLastIdentifyResult={vi.fn()}
        onOpenReviewTab={vi.fn()}
        onPreview={vi.fn()}
        onExecute={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText(/Open Camera/i));
    fireEvent.click(screen.getByText(/Open Pipeline Editor/i));

    expect(onOpenCamera).toHaveBeenCalled();
    expect(onOpenEditor).toHaveBeenCalled();
    expect(screen.getByText(/Last Identification Result/i)).toBeInTheDocument();

    rerender(
      <IdentifyTab
        pipelines={[defaultPipeline]}
        selectedPipelineId="default"
        selectedPipelineName="Default"
        defaultPipelineOption={defaultPipeline}
        processingFile={new File(['x'], 'img.png', { type: 'image/png' })}
        processingFileUrl="blob://x"
        processingSessionId="session-1"
        processingLogs={['running']}
        processingError={null}
        lastIdentifyResult={null}
        cameraInputRef={{ current: null }}
        galleryInputRef={{ current: null }}
        onSetSelectedPipelineId={vi.fn()}
        onOpenPipelineEditor={vi.fn()}
        onOpenCamera={vi.fn()}
        onHandleUpload={vi.fn()}
        onDismissProcessingError={vi.fn()}
        onClearLastIdentifyResult={vi.fn()}
        onOpenReviewTab={vi.fn()}
        onPreview={vi.fn()}
        onExecute={vi.fn()}
      />,
    );

    expect(screen.getByTestId('processing-dashboard')).toBeInTheDocument();
  });

  it('Feature: identify-tab-upload-and-fallback-pipeline | uses default pipeline option and triggers gallery input click', () => {
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(() => {});

    render(
      <IdentifyTab
        pipelines={[]}
        selectedPipelineId="default"
        selectedPipelineName="Default"
        defaultPipelineOption={defaultPipeline}
        processingFile={null}
        processingFileUrl=""
        processingSessionId={null}
        processingLogs={[]}
        processingError={null}
        lastIdentifyResult={null}
        cameraInputRef={{ current: null }}
        galleryInputRef={{ current: null }}
        onSetSelectedPipelineId={vi.fn()}
        onOpenPipelineEditor={vi.fn()}
        onOpenCamera={vi.fn()}
        onHandleUpload={vi.fn()}
        onDismissProcessingError={vi.fn()}
        onClearLastIdentifyResult={vi.fn()}
        onOpenReviewTab={vi.fn()}
        onPreview={vi.fn()}
        onExecute={vi.fn()}
      />,
    );

    expect(screen.getByDisplayValue('Default')).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Upload Files/i));
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it('Feature: identify-tab-callbacks | updates pipeline selection and forwards result card actions', () => {
    const onSetSelectedPipelineId = vi.fn();
    const onClearLastIdentifyResult = vi.fn();
    const onOpenReviewTab = vi.fn();

    render(
      <IdentifyTab
        pipelines={[defaultPipeline, { id: 'alt', name: 'Alternate' }]}
        selectedPipelineId="default"
        selectedPipelineName="Default"
        defaultPipelineOption={defaultPipeline}
        processingFile={null}
        processingFileUrl=""
        processingSessionId={null}
        processingLogs={[]}
        processingError={null}
        lastIdentifyResult={baseAsset}
        cameraInputRef={{ current: null }}
        galleryInputRef={{ current: null }}
        onSetSelectedPipelineId={onSetSelectedPipelineId}
        onOpenPipelineEditor={vi.fn()}
        onOpenCamera={vi.fn()}
        onHandleUpload={vi.fn()}
        onDismissProcessingError={vi.fn()}
        onClearLastIdentifyResult={onClearLastIdentifyResult}
        onOpenReviewTab={onOpenReviewTab}
        onPreview={vi.fn()}
        onExecute={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByDisplayValue('Default'), { target: { value: 'alt' } });
    fireEvent.click(screen.getByRole('button', { name: /Review Queue/i }));
    fireEvent.click(screen.getByRole('button', { name: /Clear/i }));

    expect(onSetSelectedPipelineId).toHaveBeenCalledWith('alt');
    expect(onOpenReviewTab).toHaveBeenCalled();
    expect(onClearLastIdentifyResult).toHaveBeenCalled();
  });

  it('Feature: review-tab-wrapper | switches queue filters and delegates pending selection mode', () => {
    const onSetQueueStatus = vi.fn();
    const onClearSelectedItems = vi.fn();
    const onFetchQueue = vi.fn();

    render(
      <ReviewTab
        queue={[baseAsset]}
        selectedItems={[]}
        loading={false}
        queueStatus="pending"
        rowVirtualizer={virtualizer as never}
        listParentRef={{ current: null }}
        onRefreshQueue={vi.fn()}
        onSetQueueStatus={onSetQueueStatus}
        onClearSelectedItems={onClearSelectedItems}
        onSelectAll={vi.fn()}
        onToggleSelection={vi.fn()}
        onBulkApprove={vi.fn()}
        onPreview={vi.fn()}
        onExecute={vi.fn()}
        onFetchQueue={onFetchQueue}
      />,
    );

    fireEvent.click(screen.getByText(/Everything/i));
    fireEvent.click(screen.getByRole('button', { name: /^Approved$/i }));

    expect(onSetQueueStatus).toHaveBeenCalledTimes(2);
    expect(onClearSelectedItems).toHaveBeenCalledTimes(2);
    expect(onFetchQueue).toHaveBeenCalledTimes(2);
    expect(screen.getByText(/Select All/i)).toBeInTheDocument();
  });
});

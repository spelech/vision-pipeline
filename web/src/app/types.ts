export interface PipelineSummary {
  id: string;
  name: string;
}

export type PipelineStageId = 'barcode' | 'vision' | 'search' | 'refine' | 'sync';

export type QueueStatus = 'all' | 'pending' | 'approved' | 'processing';

export type ActiveTab = 'identify' | 'batch' | 'review' | 'pipelines' | 'system';

export type ToastType = 'success' | 'error' | 'info';

export interface ToastState {
  message: string;
  type: ToastType;
}

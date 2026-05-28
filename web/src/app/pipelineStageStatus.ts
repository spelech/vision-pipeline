import type { PipelineStageId } from './types';

export type PipelineStageStatus = 'pending' | 'active' | 'completed';

export function getPipelineStageStatus(logs: string[], stage: PipelineStageId): PipelineStageStatus {
  const hasLog = (text: string) => logs.some((log) => log.includes(text));

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
}

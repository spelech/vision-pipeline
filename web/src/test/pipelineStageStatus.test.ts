import { describe, expect, it } from 'vitest';

import { getPipelineStageStatus } from '../app/pipelineStageStatus';

describe('getPipelineStageStatus', () => {
  it('Feature: stage-status-default | returns pending for unknown progress logs', () => {
    expect(getPipelineStageStatus([], 'barcode')).toBe('pending');
    expect(getPipelineStageStatus([], 'vision')).toBe('pending');
    expect(getPipelineStageStatus([], 'search')).toBe('pending');
    expect(getPipelineStageStatus([], 'refine')).toBe('pending');
    expect(getPipelineStageStatus([], 'sync')).toBe('pending');
  });

  it('Feature: stage-status-active | returns active for currently running stage logs', () => {
    expect(getPipelineStageStatus(['[Node: Barcode] start'], 'barcode')).toBe('active');
    expect(getPipelineStageStatus(['[Node: Vision] start'], 'vision')).toBe('active');
    expect(getPipelineStageStatus(['[Node: Search] start'], 'search')).toBe('active');
    expect(getPipelineStageStatus(['[Node: Refine] start'], 'refine')).toBe('active');
    expect(getPipelineStageStatus(['Checking for existing entries'], 'sync')).toBe('active');
  });

  it('Feature: stage-status-completed-by-downstream | marks prior stages completed when later stages begin', () => {
    expect(getPipelineStageStatus(['[Node: Vision] start'], 'barcode')).toBe('completed');
    expect(getPipelineStageStatus(['[Node: Search] start'], 'vision')).toBe('completed');
    expect(getPipelineStageStatus(['[Node: Refine] start'], 'search')).toBe('completed');
    expect(getPipelineStageStatus(['Checking for existing entries'], 'refine')).toBe('completed');
  });

  it('Feature: stage-status-finished-markers | marks all stages completed when completion markers exist', () => {
    const finishedVariants = ['🏁 done', 'pipeline finished', 'UI updating'];

    for (const marker of finishedVariants) {
      expect(getPipelineStageStatus([marker], 'barcode')).toBe('completed');
      expect(getPipelineStageStatus([marker], 'vision')).toBe('completed');
      expect(getPipelineStageStatus([marker], 'search')).toBe('completed');
      expect(getPipelineStageStatus([marker], 'refine')).toBe('completed');
      expect(getPipelineStageStatus([marker], 'sync')).toBe('completed');
    }
  });

  it('Feature: stage-status-sync-alt-log | accepts alternate sync text', () => {
    expect(getPipelineStageStatus(['found existing entries in homebox'], 'sync')).toBe('active');
  });
});

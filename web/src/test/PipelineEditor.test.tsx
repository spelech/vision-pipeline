import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PipelineEditor } from '../components/PipelineEditor';
import {
  getPipelineNodes,
  isPersistedCustomPipeline,
  getVisionPrompt,
  getRefinePrompt,
  getPromptPreview,
  type Pipeline,
} from '../components/pipelineEditorUtils';

describe('PipelineEditor', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockImplementation((url) => {
      if (url === '/api/pipelines') {
        return Promise.resolve({
          json: () => Promise.resolve({
            success: true,
            pipelines: [
              { id: 'default', name: 'Default', schema: { active_nodes: { default: ['vision'] } } }
            ]
          })
        });
      }
      if (url === '/api/config') {
         return Promise.resolve({
          json: () => Promise.resolve({
            model_favorites: ['qwen/test']
          })
        });
      }
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });
  });

  it('Feature: pipeline-editor-list | renders pipelines', async () => {
    render(<PipelineEditor />);
    expect(await screen.findByText('Pipeline Builder')).toBeInTheDocument();
    expect(await screen.findByText('Default')).toBeInTheDocument();
    expect(await screen.findByText('STAGE 1')).toBeInTheDocument();
  });

  it('Feature: pipeline-editor-create | can create a new pipeline', async () => {
    render(<PipelineEditor />);
    const btn = await screen.findByText('Create Custom');
    fireEvent.click(btn);
    // Should open modal
    expect(await screen.findByText('Pipeline Architecture')).toBeInTheDocument();
  });

  it('Feature: pipeline-editor-sync | triggers registry sync fetch', async () => {
    render(<PipelineEditor />);
    const sync = await screen.findByText('Sync Registry');
    fireEvent.click(sync);
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/pipelines');
  });

  it('Feature: pipeline-editor-edit-nodes | edits nodes by removing and adding blocks', async () => {
    render(<PipelineEditor />);

    const open = await screen.findByText('Inspect Architecture');
    fireEvent.click(open);

    expect(await screen.findByText('Pipeline Architecture')).toBeInTheDocument();

    const removeButtons = screen.getAllByText('✕');
    // First X is modal close; second is first node remove in editor list.
    fireEvent.click(removeButtons[1]);

    fireEvent.click(screen.getByText('+ scrape'));
    expect(screen.getByText('Label')).toBeInTheDocument();
  });

  it('Feature: pipeline-editor-save-error | shows alert when save fails', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
      if (url === '/api/pipelines') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            pipelines: [{ id: 'default', name: 'Default', schema: { active_nodes: { default: ['vision'] } } }]
          })
        });
      }
      if (url === '/api/config' && (!opts || !opts.method)) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ custom_pipelines: [] }) });
      }
      if (url === '/api/config' && opts?.method === 'POST') {
        return Promise.reject(new Error('save failed'));
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }) as typeof fetch;

    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<PipelineEditor />);

    fireEvent.click(await screen.findByText('Inspect Architecture'));
    fireEvent.click(await screen.findByText('Save As Custom Copy'));

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith('Failed to save pipeline');
    });
    alertSpy.mockRestore();
    globalThis.fetch = originalFetch;
  });

  it('Feature: pipeline-editor-save-copy-success | saves a non-custom pipeline as a custom copy', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
      if (url === '/api/pipelines') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            pipelines: [{ id: 'default', name: 'Default', schema: { active_nodes: { default: ['vision'] } } }]
          })
        });
      }
      if (url === '/api/config' && (!opts || !opts.method)) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ custom_pipelines: [] }) });
      }
      if (url === '/api/config' && opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }) as typeof fetch;

    render(<PipelineEditor />);
    fireEvent.click(await screen.findByText('Inspect Architecture'));
    fireEvent.click(await screen.findByText('Save As Custom Copy'));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/config', expect.objectContaining({ method: 'POST' }));
    });

    const postCall = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      (call) => call[0] === '/api/config' && call[1]?.method === 'POST'
    );
    expect(postCall).toBeDefined();

    const payload = JSON.parse((postCall?.[1] as RequestInit).body as string) as { custom_pipelines: Array<{ id: string; name: string }> };
    expect(payload.custom_pipelines).toHaveLength(1);
    expect(payload.custom_pipelines[0].id).toMatch(/^custom_/);
    expect(payload.custom_pipelines[0].name).toBe('Default Copy');

    globalThis.fetch = originalFetch;
  });

  it('Feature: pipeline-editor-vision-config | updates vision prompt through node settings and saves', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
      if (url === '/api/pipelines') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            pipelines: [{
              id: 'default',
              name: 'Default',
              schema: {
                active_nodes: { default: ['vision'] },
                custom_prompt: { default: 'Original prompt' },
              }
            }]
          })
        });
      }
      if (url === '/api/config' && (!opts || !opts.method)) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ custom_pipelines: [] }) });
      }
      if (url === '/api/config' && opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [{ id: 'qwen/model-a' }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }) as typeof fetch;

    render(<PipelineEditor />);
    fireEvent.click(await screen.findByText('Inspect Architecture'));

    fireEvent.click(screen.getAllByRole('button', { name: /vision/i })[0]);
    expect(await screen.findByText('Node Calibration')).toBeInTheDocument();

    const instructionSet = document.querySelector('textarea') as HTMLTextAreaElement;
    fireEvent.change(instructionSet, { target: { value: 'Updated vision prompt for tests' } });
    fireEvent.click(screen.getByRole('button', { name: /Confirm Parameters/i }));

    fireEvent.click(await screen.findByText('Save As Custom Copy'));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/config', expect.objectContaining({ method: 'POST' }));
    });

    const postCall = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      (call) => call[0] === '/api/config' && call[1]?.method === 'POST'
    );
    expect(postCall).toBeDefined();

    const payload = JSON.parse((postCall?.[1] as RequestInit).body as string) as {
      custom_pipelines: Array<{ schema: { custom_prompt?: { default: string } } }>;
    };
    expect(payload.custom_pipelines[0].schema.custom_prompt?.default).toBe('Updated vision prompt for tests');

    globalThis.fetch = originalFetch;
  });

  it('Feature: pipeline-editor-helpers | resolves node lists for configured, advanced, and fallback pipelines', () => {
    const configured: Pipeline = {
      id: 'configured',
      name: 'Configured',
      schema: { active_nodes: { default: ['vision', 'refine'] } },
    };
    expect(getPipelineNodes(configured)).toEqual(['vision', 'refine']);

    const advanced: Pipeline = { id: 'advanced_playwright', name: 'Advanced', schema: {} };
    expect(getPipelineNodes(advanced)).toEqual(['barcode', 'vision', 'search', 'scrape', 'refine']);

    const fallback: Pipeline = { id: 'default', name: 'Default', schema: {} };
    expect(getPipelineNodes(fallback)).toEqual(['barcode', 'vision', 'search', 'refine']);
  });

  it('Feature: pipeline-editor-helper-prompts | detects persistence flags and prompt fallbacks', () => {
    expect(isPersistedCustomPipeline({ id: 'composable', name: 'Composable', schema: {} })).toBe(true);
    expect(isPersistedCustomPipeline({ id: 'custom_123', name: 'Custom', schema: {} })).toBe(true);
    expect(isPersistedCustomPipeline({ id: 'default', name: 'Default', schema: {} })).toBe(false);

    expect(getVisionPrompt({ id: 'a', name: 'A', schema: { vision_prompt: { default: 'Vision prompt' } } })).toBe('Vision prompt');
    expect(getVisionPrompt({ id: 'a', name: 'A', schema: { custom_prompt: { default: 'Custom prompt' } } })).toBe('Custom prompt');
    expect(getVisionPrompt({ id: 'a', name: 'A', schema: {} })).toBe('');

    expect(getRefinePrompt({ id: 'a', name: 'A', schema: { refine_prompt: { default: 'Refine me' } } })).toBe('Refine me');
    expect(getRefinePrompt({ id: 'a', name: 'A', schema: {} })).toBe('');
  });

  it('Feature: pipeline-editor-helper-preview | formats prompt preview text for empty and long values', () => {
    expect(getPromptPreview('   ')).toBe('No prompt configured');
    expect(getPromptPreview('short prompt')).toBe('short prompt');

    const longPrompt = 'x'.repeat(120);
    const preview = getPromptPreview(longPrompt);
    expect(preview.endsWith('...')).toBe(true);
    expect(preview.length).toBe(93);
  });
});

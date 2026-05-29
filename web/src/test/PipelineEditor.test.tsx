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

    const open = await screen.findByText('Customize Sequence');
    fireEvent.click(open);

    expect(await screen.findByText('Pipeline Architecture')).toBeInTheDocument();

    const removeButtons = screen.getAllByText('✕');
    // First X is modal close; second is first node remove in editor list.
    fireEvent.click(removeButtons[1]);

    fireEvent.click(screen.getByText('+ scrape'));
    expect(screen.getByText('Label')).toBeInTheDocument();
  });

  it('Feature: pipeline-editor-discard | closes editor without saving when discard is clicked', async () => {
    render(<PipelineEditor />);

    fireEvent.click(await screen.findByText('Customize Sequence'));
    expect(await screen.findByText('Pipeline Architecture')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Discard'));

    await waitFor(() => {
      expect(screen.queryByText('Pipeline Architecture')).not.toBeInTheDocument();
    });
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
      if (typeof url === 'string' && url.startsWith('/api/pipelines/') && opts?.method === 'PUT') {
        return Promise.reject(new Error('save failed'));
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }) as typeof fetch;

    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<PipelineEditor />);

    fireEvent.click(await screen.findByText('Customize Sequence'));
    fireEvent.click(await screen.findByText('Save Changes'));

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith('Failed to save pipeline');
    });
    alertSpy.mockRestore();
    globalThis.fetch = originalFetch;
  });

  it('Feature: pipeline-editor-save-success | saves a pipeline through DB API endpoint', async () => {
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
      if (typeof url === 'string' && url.startsWith('/api/pipelines/') && opts?.method === 'PUT') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }) as typeof fetch;

    render(<PipelineEditor />);
    fireEvent.click(await screen.findByText('Customize Sequence'));
    fireEvent.click(await screen.findByText('Save Changes'));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/pipelines/default', expect.objectContaining({ method: 'PUT' }));
    });

    const postCall = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      (call) => call[0] === '/api/pipelines/default' && call[1]?.method === 'PUT'
    );
    expect(postCall).toBeDefined();

    const payload = JSON.parse((postCall?.[1] as RequestInit).body as string) as { name: string; schema: Record<string, unknown> };
    expect(payload.name).toBe('Default');
    expect(payload.schema).toBeDefined();

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
      if (typeof url === 'string' && url.startsWith('/api/pipelines/') && opts?.method === 'PUT') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [{ id: 'qwen/model-a' }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }) as typeof fetch;

    render(<PipelineEditor />);
    fireEvent.click(await screen.findByText('Customize Sequence'));

    fireEvent.click(screen.getAllByRole('button', { name: /vision/i })[0]);
    expect(await screen.findByText('Node Calibration')).toBeInTheDocument();

    const instructionSet = document.querySelector('textarea') as HTMLTextAreaElement;
    fireEvent.change(instructionSet, { target: { value: 'Updated vision prompt for tests' } });
    fireEvent.click(screen.getByRole('button', { name: /Confirm Parameters/i }));

    fireEvent.click(await screen.findByText('Save Changes'));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/pipelines/default', expect.objectContaining({ method: 'PUT' }));
    });

    const postCall = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      (call) => call[0] === '/api/pipelines/default' && call[1]?.method === 'PUT'
    );
    expect(postCall).toBeDefined();

    const payload = JSON.parse((postCall?.[1] as RequestInit).body as string) as {
      schema: { custom_prompt?: { default: string } };
    };
    expect(payload.schema.custom_prompt?.default).toBe('Updated vision prompt for tests');

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

  it('Feature: pipeline-editor-save-existing-custom | saves persisted custom pipeline without creating copy', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
      if (url === '/api/pipelines') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            pipelines: [{ id: 'custom_user_flow', name: 'My Flow', schema: { active_nodes: { default: ['vision', 'refine'] } } }]
          })
        });
      }
      if (typeof url === 'string' && url.startsWith('/api/pipelines/') && opts?.method === 'PUT') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [{ id: 'qwen/model-a' }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }) as typeof fetch;

    render(<PipelineEditor />);
    fireEvent.click(await screen.findByText('Customize Sequence'));
    fireEvent.click(await screen.findByText('Save Changes'));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/pipelines/custom_user_flow', expect.objectContaining({ method: 'PUT' }));
    });

    const postCall = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      (call) => call[0] === '/api/pipelines/custom_user_flow' && call[1]?.method === 'PUT'
    );
    const payload = JSON.parse((postCall?.[1] as RequestInit).body as string) as { name: string };
    expect(payload.name).toBe('My Flow');

    globalThis.fetch = originalFetch;
  });

  it('Feature: pipeline-editor-create-fallback-model | uses fallback vision model when no model catalog loaded', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/pipelines') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, pipelines: [] }) });
      }
      if (url === '/api/config') {
        return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }) as typeof fetch;

    render(<PipelineEditor />);
    fireEvent.click(await screen.findByText('Create Custom'));
    fireEvent.click(screen.getAllByRole('button', { name: /vision/i })[0]);

    const select = screen.getByRole('combobox') as HTMLSelectElement;
    expect(select.value).toBe('qwen/qwen2.5-vl-72b-instruct');

    globalThis.fetch = originalFetch;
  });

  it('Feature: pipeline-editor-node-config-variants | opens refine, scrape, and system-managed node config states', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/pipelines') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            pipelines: [
              {
                id: 'custom_flow',
                name: 'Custom Flow',
                schema: {
                  active_nodes: { default: ['barcode', 'vision', 'search', 'scrape', 'refine'] },
                  vision_prompt: { default: 'vision' },
                  refine_prompt: { default: 'refine' },
                  scrape_wait_time: { default: 2000 },
                },
              },
            ],
          }),
        });
      }
      if (url === '/api/config') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ model_favorites: ['qwen/a'] }) });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [{ id: 'qwen/a' }] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }) as typeof fetch;

    render(<PipelineEditor />);
    fireEvent.click(await screen.findByText('Customize Sequence'));

    fireEvent.click(screen.getAllByRole('button', { name: /refine/i })[0]);
    expect(await screen.findByText(/Merge logic instructions/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Confirm Parameters/i }));

    fireEvent.click(screen.getAllByRole('button', { name: /scrape/i })[0]);
    expect(await screen.findByText(/JavaScript Wait Time/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Confirm Parameters/i }));

    fireEvent.click(screen.getAllByRole('button', { name: /search/i })[0]);
    expect(await screen.findByText(/Node calibrated by system core/i)).toBeInTheDocument();

    globalThis.fetch = originalFetch;
  });

  it('Feature: pipeline-editor-subtitles | renders subtitle variants for default, advanced, and custom pipelines', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/pipelines') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            pipelines: [
              { id: 'default', name: 'Default', schema: {} },
              { id: 'advanced_playwright', name: 'Advanced', schema: {} },
              { id: 'custom_user', name: 'Custom', schema: { active_nodes: { default: ['vision'] } } },
            ],
          }),
        });
      }
      if (url === '/api/config') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ model_favorites: [] }) });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }) as typeof fetch;

    render(<PipelineEditor />);

    expect(await screen.findByText(/Core System Sequence/i)).toBeInTheDocument();
    expect(screen.getByText(/Advanced Scraping Flow/i)).toBeInTheDocument();
    expect(screen.getByText(/Configurable User Flow/i)).toBeInTheDocument();

    globalThis.fetch = originalFetch;
  });
});

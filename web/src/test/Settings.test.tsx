import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Settings } from '../components/Settings';
import { normalizePromptTemplates, derivePromptTemplatesFromPipelines } from '../components/settingsUtils';

describe('Settings', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockImplementation((url) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            secrets_status: { OPENROUTER_API_KEY: true },
            model_favorites: ['qwen/qwen2.5-vl-72b-instruct'],
            starred_models: [],
            image_optimization: { max_dimension: 1024, quality: 85 },
            prompt_templates: [{ id: '1', name: 'Default', prompt: 'Analyze' }]
          })
        });
      }
      if (url === '/api/models') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            models: [{ id: 'qwen/qwen2.5-vl-72b-instruct' }],
          }),
        });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true, pipelines: [] }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
  });

  it('Feature: settings-load | renders correctly and loads data', async () => {
    render(<Settings />);
    expect(await screen.findByText('System Settings')).toBeInTheDocument();
    
    // Config items should load
    expect(await screen.findByText('qwen2.5-vl-72b-instruct')).toBeInTheDocument();
    
    // Wait for prompts to load
    expect(await screen.findByDisplayValue('Default')).toBeInTheDocument();
  });

  it('Feature: settings-model-add | allows adding a new model', async () => {
    render(<Settings />);
    await screen.findByText('System Settings');

    // Find the input with placeholder
    const modelInput = screen.getByPlaceholderText('owner/model-name');
    fireEvent.change(modelInput, { target: { value: 'new/model' } });
    
    const addButton = screen.getByText('Add');
    fireEvent.click(addButton);

    expect(await screen.findByText('model')).toBeInTheDocument();
  });

  it('Feature: settings-save | allows saving settings', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url, opts) => {
      if (url === '/api/config' && opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            secrets_status: {},
            model_favorites: [],
            starred_models: [],
            image_optimization: { max_dimension: 1024, quality: 85 },
            prompt_templates: []
          })
        });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [] }) });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, pipelines: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<Settings />);
    await screen.findByText('System Settings');

    const saveButton = screen.getByText('Apply Full Configuration');
    
    // mock window.alert
    const spyAlert = vi.spyOn(window, 'alert').mockImplementation(() => {});

    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/config', expect.objectContaining({ method: 'POST' }));
    });
    
    expect(spyAlert).toHaveBeenCalledWith('Settings saved successfully!');
    // cleanup
    spyAlert.mockRestore();
  });

  it('Feature: settings-derived-prompts | derives prompt templates from pipeline schema when config templates are absent', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            secrets_status: {},
            model_favorites: [],
            starred_models: [],
            image_optimization: { max_dimension: 1024, quality: 85 },
            prompt_templates: []
          })
        });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [] }) });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            pipelines: [
              {
                id: 'default',
                name: 'Default Vision Pipeline',
                schema: {
                  vision_prompt: { default: 'vision instructions' },
                  refine_prompt: { default: 'refine instructions' }
                }
              },
              {
                id: 'receipt',
                name: 'Receipt Pipeline',
                schema: {
                  vision_prompt: { default: 'receipt vision instructions' },
                  refine_prompt: { default: 'receipt refine instructions' }
                }
              }
            ]
          }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<Settings />);
    expect(await screen.findByDisplayValue(/Default Vision Pipeline vision prompt/i)).toBeInTheDocument();
    expect(await screen.findByDisplayValue(/Default Vision Pipeline refine prompt/i)).toBeInTheDocument();
    expect(await screen.findByDisplayValue(/Receipt Pipeline vision prompt/i)).toBeInTheDocument();
    expect(await screen.findByDisplayValue(/Receipt Pipeline refine prompt/i)).toBeInTheDocument();
  });

  it('Feature: settings-star-remove | toggles star and removes model from registry', async () => {
    render(<Settings />);
    await screen.findByText('System Settings');

    const emptyStar = screen.getByText('☆');
    fireEvent.click(emptyStar);
    expect(screen.getByText('★')).toBeInTheDocument();

    fireEvent.click(screen.getByText('✕'));
    expect(screen.queryByText('qwen2.5-vl-72b-instruct')).not.toBeInTheDocument();
  });

  it('Feature: settings-save-error | shows error alert when save fails', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url, opts) => {
      if (url === '/api/config' && opts?.method === 'POST') {
        return Promise.reject(new Error('save failed'));
      }
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            secrets_status: {},
            model_favorites: [],
            starred_models: [],
            image_optimization: { max_dimension: 1024, quality: 85 },
            prompt_templates: []
          })
        });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [] }) });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, pipelines: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<Settings />);
    await screen.findByText('System Settings');

    fireEvent.click(screen.getByText('Apply Full Configuration'));

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith('Failed to save settings.');
    });
    alertSpy.mockRestore();
  });

  it('Feature: settings-save-without-templates | omits prompt_templates when none are configured', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url, opts) => {
      if (url === '/api/config' && opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            secrets_status: {},
            model_favorites: [],
            starred_models: [],
            image_optimization: { max_dimension: 1024, quality: 85 },
            prompt_templates: []
          })
        });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: false, models: [] }) });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, pipelines: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<Settings />);
    await screen.findByText('System Settings');

    fireEvent.click(screen.getByText('Apply Full Configuration'));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/config', expect.objectContaining({ method: 'POST' }));
    });

    const postCall = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      (call) => call[0] === '/api/config' && call[1]?.method === 'POST'
    );
    expect(postCall).toBeDefined();

    const payload = JSON.parse((postCall?.[1] as RequestInit).body as string) as Record<string, unknown>;
    expect(Object.prototype.hasOwnProperty.call(payload, 'prompt_templates')).toBe(false);

    alertSpy.mockRestore();
  });

  it('Feature: settings-template-format-add | formats and creates prompt templates from the editor', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<Settings />);
    await screen.findByText('System Settings');

    const promptTextAreas = screen.getAllByRole('textbox').filter((el) => el.tagName.toLowerCase() === 'textarea');
    fireEvent.change(promptTextAreas[0], { target: { value: '  Keep this trimmed  ' } });
    fireEvent.click(screen.getByText('Format'));

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith('Formatted template!');
    });
    expect((promptTextAreas[0] as HTMLTextAreaElement).value).toBe('Keep this trimmed');

    fireEvent.click(screen.getByText('Delete'));
    fireEvent.click(screen.getByText('Initialize Template'));

    expect(await screen.findByDisplayValue('NEW TEMPLATE')).toBeInTheDocument();
    alertSpy.mockRestore();
  });

  it('Feature: settings-template-normalize | normalizes array/object and handles invalid template values', () => {
    expect(normalizePromptTemplates([{ id: '1', name: 'A', prompt: 'P' }])).toEqual([{ id: '1', name: 'A', prompt: 'P' }]);

    expect(normalizePromptTemplates({
      my_prompt: 'Use this prompt',
      secondary_prompt: 'Second',
    })).toEqual([
      { id: 'my_prompt', name: 'MY PROMPT', prompt: 'Use this prompt' },
      { id: 'secondary_prompt', name: 'SECONDARY PROMPT', prompt: 'Second' },
    ]);

    expect(normalizePromptTemplates('invalid')).toEqual([]);
    expect(normalizePromptTemplates(null)).toEqual([]);
  });

  it('Feature: settings-template-derive | derives prompt templates from pipeline schema prompt keys only', () => {
    const derived = derivePromptTemplatesFromPipelines([
      {
        id: 'default',
        name: 'Default Vision Pipeline',
        schema: {
          vision_prompt: { default: 'vision text' },
          refine_prompt: { default: 'refine text' },
          vision_model: { default: 'qwen/x' },
        },
      },
      {
        id: 'receipt',
        name: 'Receipt Pipeline',
        schema: {
          vision_prompt: { default: 'receipt vision' },
          refine_prompt: { default: 'receipt refine' },
          active_nodes: { default: [] },
        },
      },
      {
        id: 'secondary',
        name: 'Secondary',
        schema: {},
      },
    ]);

    expect(derived).toEqual([
      {
        id: 'default-vision_prompt',
        name: 'Default Vision Pipeline vision prompt',
        prompt: 'vision text',
      },
      {
        id: 'default-refine_prompt',
        name: 'Default Vision Pipeline refine prompt',
        prompt: 'refine text',
      },
      {
        id: 'receipt-vision_prompt',
        name: 'Receipt Pipeline vision prompt',
        prompt: 'receipt vision',
      },
      {
        id: 'receipt-refine_prompt',
        name: 'Receipt Pipeline refine prompt',
        prompt: 'receipt refine',
      },
    ]);

    expect(derivePromptTemplatesFromPipelines(undefined)).toEqual([]);
  });

  it('Feature: settings-secret-visibility | keeps URLs visible while masking key/token secrets', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url) => {
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            secrets_status: {
              HOMEBOX_URL: 'https://homebox.local',
              OPENROUTER_API_KEY: true,
            },
            model_favorites: [],
            starred_models: [],
            image_optimization: { max_dimension: 1024, quality: 85 },
            prompt_templates: [],
          }),
        });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [] }) });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, pipelines: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<Settings />);
    expect(await screen.findByDisplayValue('https://homebox.local')).toBeInTheDocument();
    expect(screen.getByDisplayValue('********')).toBeInTheDocument();
  });

  it('Feature: settings-model-add-duplicate | does not add a duplicate model id', async () => {
    render(<Settings />);
    await screen.findByText('System Settings');

    const modelInput = screen.getByPlaceholderText('owner/model-name');
    fireEvent.change(modelInput, { target: { value: 'qwen/qwen2.5-vl-72b-instruct' } });
    fireEvent.click(screen.getByText('Add'));

    expect(screen.getAllByText('qwen2.5-vl-72b-instruct')).toHaveLength(1);
  });

  it('Feature: settings-load-fallback | keeps UI stable when config/models/pipelines requests fail', async () => {
    globalThis.fetch = vi.fn().mockImplementation(() => Promise.reject(new Error('network down')));

    render(<Settings />);

    expect(await screen.findByText('System Settings')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('owner/model-name')).toBeInTheDocument();
    expect(screen.getByText('Apply Full Configuration')).toBeInTheDocument();
  });

  it('Feature: settings-save-empty-template-array | persists prompt_templates as empty when templates originated from config', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url, opts) => {
      if (url === '/api/config' && opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            secrets_status: {},
            model_favorites: ['qwen/qwen2.5-vl-72b-instruct'],
            starred_models: [],
            image_optimization: { max_dimension: 1024, quality: 85 },
            prompt_templates: [{ id: 'seed', name: 'Seed', prompt: 'Prompt' }],
          }),
        });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [] }) });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, pipelines: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<Settings />);
    await screen.findByText('System Settings');

    fireEvent.click(screen.getByText('Delete'));
    fireEvent.click(screen.getByText('Apply Full Configuration'));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/config', expect.objectContaining({ method: 'POST' }));
    });

    const postCall = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      (call) => call[0] === '/api/config' && call[1]?.method === 'POST'
    );
    const payload = JSON.parse((postCall?.[1] as RequestInit).body as string) as Record<string, unknown>;
    expect(payload.prompt_templates).toEqual([]);

    alertSpy.mockRestore();
  });

  it('Feature: settings-save-updated-secret-and-image-optimization | persists edited secret key and optimization values', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url, opts) => {
      if (url === '/api/config' && opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            secrets_status: {
              OPENROUTER_API_KEY: true,
            },
            model_favorites: [],
            starred_models: [],
            image_optimization: { max_dimension: 1024, quality: 85 },
            prompt_templates: [],
          }),
        });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [] }) });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, pipelines: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<Settings />);
    await screen.findByText('System Settings');

    fireEvent.change(screen.getByPlaceholderText(/Enter OPENROUTER API KEY/i), { target: { value: 'test-key-123' } });
    fireEvent.change(screen.getByDisplayValue('1024'), { target: { value: '1600' } });
    fireEvent.change(screen.getByDisplayValue('85'), { target: { value: '92' } });

    fireEvent.click(screen.getByText('Apply Full Configuration'));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/config', expect.objectContaining({ method: 'POST' }));
    });

    const postCall = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      (call) => call[0] === '/api/config' && call[1]?.method === 'POST'
    );
    const payload = JSON.parse((postCall?.[1] as RequestInit).body as string) as {
      OPENROUTER_API_KEY: string;
      image_optimization: { max_dimension: number; quality: number };
    };
    expect(payload.OPENROUTER_API_KEY).toBe('test-key-123');
    expect(payload.image_optimization).toEqual({ max_dimension: 1600, quality: 92 });

    alertSpy.mockRestore();
  });

  it('Feature: settings-gmail-auto-sync-payload | persists gmail scheduler settings', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url, opts) => {
      if (url === '/api/config' && opts?.method === 'POST') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            secrets_status: { OPENROUTER_API_KEY: true },
            model_favorites: [],
            starred_models: [],
            image_optimization: { max_dimension: 1024, quality: 85 },
            prompt_templates: [],
            gmail_auto_sync_enabled: false,
            gmail_poll_interval_minutes: 30,
            gmail_auto_sync_query: 'subject:receipt',
            gmail_auto_sync_max_results: 10,
          }),
        });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [] }) });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, pipelines: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<Settings />);
    await screen.findByText('System Settings');

    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.change(screen.getByDisplayValue('30'), { target: { value: '45' } });
    fireEvent.change(screen.getByDisplayValue('subject:receipt'), { target: { value: 'subject:invoice' } });
    fireEvent.change(screen.getByDisplayValue('10'), { target: { value: '35' } });
    fireEvent.click(screen.getByText('Apply Full Configuration'));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/config', expect.objectContaining({ method: 'POST' }));
    });

    const postCall = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.find(
      (call) => call[0] === '/api/config' && call[1]?.method === 'POST'
    );
    const payload = JSON.parse((postCall?.[1] as RequestInit).body as string) as Record<string, unknown>;
    expect(payload.gmail_auto_sync_enabled).toBe(true);
    expect(payload.gmail_poll_interval_minutes).toBe(45);
    expect(payload.gmail_auto_sync_query).toBe('subject:invoice');
    expect(payload.gmail_auto_sync_max_results).toBe(35);

    alertSpy.mockRestore();
  });

  it('Feature: settings-connect-gmail | opens auth url from backend when connect is clicked', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url, opts) => {
      if (url === '/api/gmail/auth-url' && opts?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ auth_url: 'https://accounts.google.com/o/oauth2/v2/auth?x=1' }),
        });
      }
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            secrets_status: {},
            model_favorites: [],
            starred_models: [],
            image_optimization: { max_dimension: 1024, quality: 85 },
            prompt_templates: [],
          }),
        });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [] }) });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, pipelines: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    render(<Settings />);
    await screen.findByText('System Settings');

    fireEvent.click(screen.getByText('Connect Gmail'));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/gmail/auth-url', expect.objectContaining({ method: 'POST' }));
    });
    expect(openSpy).toHaveBeenCalledWith(
      'https://accounts.google.com/o/oauth2/v2/auth?x=1',
      '_blank',
      'noopener,noreferrer'
    );
    openSpy.mockRestore();
  });

  it('Feature: settings-connect-gmail-error | shows alert when auth url request fails', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url, opts) => {
      if (url === '/api/gmail/auth-url' && opts?.method === 'POST') {
        return Promise.resolve({
          ok: false,
          json: () => Promise.resolve({ detail: 'OAuth is not configured' }),
        });
      }
      if (url === '/api/config') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            secrets_status: {},
            model_favorites: [],
            starred_models: [],
            image_optimization: { max_dimension: 1024, quality: 85 },
            prompt_templates: [],
          }),
        });
      }
      if (url === '/api/models') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, models: [] }) });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, pipelines: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<Settings />);
    await screen.findByText('System Settings');

    fireEvent.click(screen.getByText('Connect Gmail'));

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith('OAuth is not configured');
    });
    alertSpy.mockRestore();
  });
});

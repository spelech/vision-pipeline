import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Settings } from '../components/Settings';

describe('Settings', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockImplementation((url) => {
      if (url === '/api/config') {
        return Promise.resolve({
          json: () => Promise.resolve({
            secrets_status: { OPENROUTER_API_KEY: true },
            model_favorites: ['qwen/qwen2.5-vl-72b-instruct'],
            starred_models: [],
            image_optimization: { max_dimension: 1024, quality: 85 },
            prompt_templates: [{ id: '1', name: 'Default', prompt: 'Analyze' }]
          })
        });
      }
      return Promise.resolve({ json: () => Promise.resolve({}) });
    });
  });

  it('renders correctly and loads data', async () => {
    render(<Settings />);
    expect(await screen.findByText('System Settings')).toBeInTheDocument();
    
    // Config items should load
    expect(await screen.findByText('qwen2.5-vl-72b-instruct')).toBeInTheDocument();
    
    // Wait for prompts to load
    await waitFor(() => {
      const inputs = screen.getAllByRole('textbox');
      expect(inputs.some(i => (i as HTMLInputElement).value === 'Default')).toBe(true);
    });
  });

  it('allows adding a new model', async () => {
    render(<Settings />);
    await screen.findByText('System Settings');

    const inputs = screen.getAllByRole('textbox');
    // Find the input with placeholder
    const modelInput = screen.getByPlaceholderText('owner/model-name');
    fireEvent.change(modelInput, { target: { value: 'new/model' } });
    
    const addButton = screen.getByText('Add');
    fireEvent.click(addButton);

    expect(await screen.findByText('model')).toBeInTheDocument();
  });

  it('allows saving settings', async () => {
    let fetchBody = '';
    globalThis.fetch = vi.fn().mockImplementation((url, opts) => {
      if (url === '/api/config' && opts?.method === 'POST') {
        fetchBody = opts.body;
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }
      if (url === '/api/config') {
        return Promise.resolve({
          json: () => Promise.resolve({
            secrets_status: {},
            model_favorites: [],
            starred_models: [],
            image_optimization: { max_dimension: 1024, quality: 85 },
            prompt_templates: []
          })
        });
      }
      return Promise.resolve({ json: () => Promise.resolve({}) });
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
});

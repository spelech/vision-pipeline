import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PipelineEditor } from '../components/PipelineEditor';

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

  it('renders pipelines', async () => {
    render(<PipelineEditor />);
    expect(await screen.findByText('Pipeline Builder')).toBeInTheDocument();
    expect(await screen.findByText('Default')).toBeInTheDocument();
    expect(await screen.findByText('STAGE 1')).toBeInTheDocument();
  });

  it('can create a new pipeline', async () => {
    render(<PipelineEditor />);
    const btn = await screen.findByText('Create Custom');
    fireEvent.click(btn);
    // Should open modal
    expect(await screen.findByText('Pipeline Architecture')).toBeInTheDocument();
  });
});

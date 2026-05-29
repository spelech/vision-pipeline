import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AssetCard } from '../components/AssetCard';
import type { Asset } from '../types';

describe('AssetCard', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ logs: [] }),
    });
  });

  const mockItem: Asset = {
    id: '1',
    image_path: 'test-image.jpg',
    status: 'pending',
    product_type: 'food',
    ai_output: {
      llm_output: { product_name: 'Test Food', brand: 'Test Brand', category: 'Snack', description: 'desc' }
    },
    user_overrides: {},
    selected_services: ['homebox']
  };

  it('Feature: asset-card-collapsed | renders collapsed state correctly', () => {
    render(<AssetCard item={mockItem} onPreview={vi.fn()} onExecute={vi.fn()} />);
    expect(screen.getByText('Test Food')).toBeInTheDocument();
    expect(screen.getByText('test-image.jpg')).toBeInTheDocument();
    expect(screen.getByText('food')).toBeInTheDocument();
    
    // Check that expanded fields are not visible
    expect(screen.queryByLabelText('Brand')).not.toBeInTheDocument();
  });

  it('Feature: asset-card-expand | expands when clicking the chevron', () => {
    render(<AssetCard item={mockItem} onPreview={vi.fn()} onExecute={vi.fn()} />);
    const expandBtn = screen.getByLabelText('Expand Asset');
    fireEvent.click(expandBtn);

    expect(screen.getByDisplayValue('Test Brand')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Snack')).toBeInTheDocument();
    expect(screen.getByDisplayValue('desc')).toBeInTheDocument();
  });

  it('Feature: asset-card-execute | updates edit data and fires onExecute with overrides', () => {
    const handleExecute = vi.fn();
    render(<AssetCard item={mockItem} onPreview={vi.fn()} onExecute={handleExecute} />);
    
    fireEvent.click(screen.getByLabelText('Expand Asset'));
    
    const brandInput = screen.getByDisplayValue('Test Brand');
    fireEvent.change(brandInput, { target: { value: 'New Brand' } });
    
    fireEvent.click(screen.getByText(/Execute & Sync/i));
    
    expect(handleExecute).toHaveBeenCalledWith(
      ['homebox'],
      expect.objectContaining({ brand: 'New Brand', product_name: 'Test Food' })
    );
  });

  it('Feature: asset-card-select | toggles selection', () => {
    const handleToggleSelect = vi.fn();
    const { container } = render(<AssetCard item={mockItem} isSelected={false} onToggleSelect={handleToggleSelect} onPreview={vi.fn()} onExecute={vi.fn()} />);
    
    // Since there's no aria-label, we can find it by className or click early element
    // It's the first div inside the p-6 div that handles toggle
    const toggleDiv = container.querySelector('.cursor-pointer');
    fireEvent.click(toggleDiv!);
    expect(handleToggleSelect).toHaveBeenCalled();
  });

  it('Feature: asset-card-preview | uses first selected service for preview', () => {
    const handlePreview = vi.fn();
    render(<AssetCard item={mockItem} onPreview={handlePreview} onExecute={vi.fn()} />);

    fireEvent.click(screen.getByLabelText('Expand Asset'));
    fireEvent.click(screen.getByText(/Preview Payload/i));

    expect(handlePreview).toHaveBeenCalledWith('homebox', expect.objectContaining({ product_name: 'Test Food' }));
  });

  it('Feature: asset-card-technical-toggle | shows technical payload JSON when toggled', () => {
    render(<AssetCard item={mockItem} onPreview={vi.fn()} onExecute={vi.fn()} />);

    fireEvent.click(screen.getByLabelText('Expand Asset'));
    fireEvent.click(screen.getByText(/Show Technical Data/i));

    expect(screen.getByText(/"llm_output"/i)).toBeInTheDocument();
  });

  it('Feature: asset-card-service-empty | disables actions when no services are selected', () => {
    render(<AssetCard item={mockItem} onPreview={vi.fn()} onExecute={vi.fn()} />);

    fireEvent.click(screen.getByLabelText('Expand Asset'));

    fireEvent.click(screen.getByLabelText(/Enable Homebox/i));

    expect(screen.getByRole('button', { name: /Preview Payload/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Execute & Sync/i })).toBeDisabled();
  });

  it('Feature: asset-card-open-image | opens original upload in new tab from thumbnail', () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    const { container } = render(<AssetCard item={mockItem} onPreview={vi.fn()} onExecute={vi.fn()} />);

    const imagePanel = container.querySelector('.w-24.h-24.cursor-pointer') as HTMLElement;
    fireEvent.click(imagePanel);

    expect(openSpy).toHaveBeenCalledWith('/uploads/test-image.jpg', '_blank');
    openSpy.mockRestore();
  });

  it('Feature: asset-card-log-session-id | fetches logs using ai_output session id when expanded', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ logs: [{ message: '[Node: Vision] complete' }] }),
    });

    render(<AssetCard item={{ ...mockItem, ai_output: { ...mockItem.ai_output, session_id: 'sess-42' } }} onPreview={vi.fn()} onExecute={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Expand Asset'));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/logs/sess-42');
      expect(screen.getByText(/\[Node: Vision\] complete/i)).toBeInTheDocument();
    });
  });

  it('Feature: asset-card-log-fallback-session | falls back to batch-item session id when no ai session id', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ logs: [] }),
    });

    render(<AssetCard item={{ ...mockItem, ai_output: { llm_output: {} } }} onPreview={vi.fn()} onExecute={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Expand Asset'));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/logs/batch-item-1');
    });
  });

  it('Feature: asset-card-log-fetch-error | handles log fetch failures', async () => {
    const err = new Error('network fail');
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    globalThis.fetch = vi.fn().mockRejectedValue(err);

    render(<AssetCard item={mockItem} onPreview={vi.fn()} onExecute={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Expand Asset'));

    await waitFor(() => {
      expect(errSpy).toHaveBeenCalledWith('Failed to fetch logs', err);
    });
  });

  it('Feature: asset-card-default-service | does not enable any default service when none are selected', () => {
    const handlePreview = vi.fn();
    render(<AssetCard item={{ ...mockItem, selected_services: [] }} onPreview={handlePreview} onExecute={vi.fn()} />);

    fireEvent.click(screen.getByLabelText('Expand Asset'));
    expect(screen.getByRole('button', { name: /Preview Payload/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Execute & Sync/i })).toBeDisabled();

    expect(handlePreview).not.toHaveBeenCalled();
  });

  it('Feature: asset-card-service-generation-success | generates service output when enabling a new service', async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/service-output/generate') {
        return {
          ok: true,
          json: async () => ({
            success: true,
            output: {
              status: 'ready',
              data: { recipe_ingredients_raw: 'Eggs\nFlour' }
            }
          })
        } as Response;
      }
      return {
        ok: true,
        json: async () => ({ logs: [] })
      } as Response;
    });

    render(<AssetCard item={{ ...mockItem, selected_services: [] }} onPreview={vi.fn()} onExecute={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Expand Asset'));
    fireEvent.click(screen.getByLabelText(/Enable Mealie/i));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        '/api/service-output/generate',
        expect.objectContaining({ method: 'POST' })
      );
    });

    await waitFor(() => {
      expect(screen.getByLabelText(/Ingredients \(one per line\)/i)).toBeInTheDocument();
    });
  });

  it('Feature: asset-card-service-generation-error | shows retry state when service generation fails', async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/service-output/generate') {
        return {
          ok: false,
          json: async () => ({ success: false, error: 'failed' })
        } as Response;
      }
      return {
        ok: true,
        json: async () => ({ logs: [] })
      } as Response;
    });

    render(<AssetCard item={{ ...mockItem, selected_services: [] }} onPreview={vi.fn()} onExecute={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Expand Asset'));
    fireEvent.click(screen.getByLabelText(/Enable Mealie/i));

    await waitFor(() => {
      expect(screen.getByText(/Service generation failed/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /Retry Service Run/i })).toBeInTheDocument();
  });
});

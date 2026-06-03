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

  it('Feature: asset-card-delete | exposes a delete action when provided', () => {
    const handleDelete = vi.fn();

    render(<AssetCard item={mockItem} onDelete={handleDelete} onPreview={vi.fn()} onExecute={vi.fn()} />);

    fireEvent.click(screen.getByLabelText('Delete Asset'));

    expect(handleDelete).toHaveBeenCalledTimes(1);
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
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ item_id: 1, service_name: 'mealie', force: true })
        })
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

  it('Feature: asset-card-service-toggle-off | does not regenerate service output when disabling a selected service', async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/service-output/generate') {
        return {
          ok: true,
          json: async () => ({
            success: true,
            output: {
              status: 'ready',
              data: { notes: 'Stored item' }
            }
          })
        } as Response;
      }
      return {
        ok: true,
        json: async () => ({ logs: [] })
      } as Response;
    });

    render(<AssetCard item={mockItem} onPreview={vi.fn()} onExecute={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Expand Asset'));
    fireEvent.click(screen.getByLabelText(/Enable Homebox/i));

    await waitFor(() => {
      expect(screen.queryByLabelText(/Homebox Notes/i)).not.toBeInTheDocument();
    });

    expect(globalThis.fetch).not.toHaveBeenCalledWith(
      '/api/service-output/generate',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('Feature: asset-card-homebox-object-fields | renders object technical details as JSON text', async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/service-output/generate') {
        return {
          ok: true,
          json: async () => ({
            success: true,
            output: {
              status: 'ready',
              data: { technical_details: { wattage: '10W', color: 'warm white' } }
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
    fireEvent.click(screen.getByLabelText(/Enable Homebox/i));

    await waitFor(() => {
      const technicalField = screen.getByLabelText(/Technical Details/i) as HTMLTextAreaElement;
      expect(technicalField.value).toContain('"wattage": "10W"');
      expect(technicalField.value).toContain('"color": "warm white"');
    });
  });

  it('Feature: asset-card-review-image-precedence | opens review image data uri when available', () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    const reviewDataUri = 'data:image/jpeg;base64,Zm9v';

    const { container } = render(
      <AssetCard
        item={{
          ...mockItem,
          image_path: 'relative.jpg',
          ai_output: { ...mockItem.ai_output, review_image_data_uri: reviewDataUri },
        }}
        onPreview={vi.fn()}
        onExecute={vi.fn()}
      />,
    );

    const imagePanel = container.querySelector('.w-24.h-24.cursor-pointer') as HTMLElement;
    fireEvent.click(imagePanel);

    expect(openSpy).toHaveBeenCalledWith(reviewDataUri, '_blank');
    openSpy.mockRestore();
  });

  it('Feature: asset-card-data-uri-image-path | opens data uri image path directly', () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    const dataUriPath = 'data:image/png;base64,YmFy';

    const { container } = render(
      <AssetCard
        item={{ ...mockItem, image_path: dataUriPath, ai_output: { llm_output: {} } }}
        onPreview={vi.fn()}
        onExecute={vi.fn()}
      />,
    );

    const imagePanel = container.querySelector('.w-24.h-24.cursor-pointer') as HTMLElement;
    fireEvent.click(imagePanel);

    expect(openSpy).toHaveBeenCalledWith(dataUriPath, '_blank');
    openSpy.mockRestore();
  });

  it('Feature: asset-card-service-retry | retries generation and enables changedetection fields', async () => {
    const generation = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ success: false, error: 'first run failed' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, output: { status: 'ready', data: { product_url: 'https://shop/item' } } }),
      });

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/service-output/generate') {
        return (await generation()) as Response;
      }
      return {
        ok: true,
        json: async () => ({ logs: [] }),
      } as Response;
    });

    render(<AssetCard item={{ ...mockItem, selected_services: [] }} onPreview={vi.fn()} onExecute={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Expand Asset'));
    fireEvent.click(screen.getByLabelText(/Enable CD.io/i));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Retry Service Run/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Retry Service Run/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/Expand CD.io details/i)).toBeEnabled();
    });

    expect(await screen.findByLabelText(/Product URL/i)).toBeInTheDocument();
    expect(await screen.findByLabelText(/Check Every \(hours\)/i)).toBeInTheDocument();
  });

  it('Feature: asset-card-stage-status | reflects pending active completed and failed stages from logs', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        logs: [
          { message: '[Node: Barcode] started' },
          { message: '[Node: Vision] started' },
          { message: '[Node: Search] ❌ failed' },
          { message: 'Checking for existing entries' },
          { message: '🏁 finished' },
        ],
      }),
    });

    render(<AssetCard item={mockItem} onPreview={vi.fn()} onExecute={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Expand Asset'));

    await waitFor(() => {
      expect(screen.getByText(/Services Sync Check/i)).toBeInTheDocument();
    });
    expect(screen.getAllByText(/Failed/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Completed/i).length).toBeGreaterThan(0);
  });

  it('Feature: asset-card-pricebuddy-fields | renders editable price-tracking fields after generation succeeds', async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/service-output/generate') {
        return {
          ok: true,
          json: async () => ({
            success: true,
            output: {
              status: 'ready',
              data: {
                target_price: '19.99',
                currency: 'USD',
                retailer: 'Example Shop',
              },
            },
          }),
        } as Response;
      }
      return { ok: true, json: async () => ({ logs: [] }) } as Response;
    });

    render(<AssetCard item={{ ...mockItem, selected_services: [] }} onPreview={vi.fn()} onExecute={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Expand Asset'));
    fireEvent.click(screen.getByLabelText(/Enable Price/i));

    await waitFor(() => {
      expect(screen.getByLabelText(/Expand Price details/i)).toBeEnabled();
    });

    expect(await screen.findByDisplayValue('19.99')).toBeInTheDocument();
    expect(await screen.findByDisplayValue('USD')).toBeInTheDocument();
    expect(await screen.findByDisplayValue('Example Shop')).toBeInTheDocument();
  });

  it('Feature: asset-card-preview-priority | prefers expanded ready service when selecting preview payload', () => {
    const handlePreview = vi.fn();
    render(
      <AssetCard
        item={{ ...mockItem, selected_services: ['homebox', 'mealie'] }}
        onPreview={handlePreview}
        onExecute={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByLabelText('Expand Asset'));
    fireEvent.click(screen.getByLabelText(/Expand Mealie details/i));
    fireEvent.click(screen.getByRole('button', { name: /Preview Payload/i }));

    expect(handlePreview).toHaveBeenCalledWith('mealie', expect.any(Object));
  });

  it('Feature: asset-card-running-disable | disables execute while service generation is in running state', async () => {
    globalThis.fetch = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/service-output/generate') {
        return new Promise<Response>(() => undefined);
      }
      return Promise.resolve({ ok: true, json: async () => ({ logs: [] }) } as Response);
    }) as typeof fetch;

    render(<AssetCard item={{ ...mockItem, selected_services: [] }} onPreview={vi.fn()} onExecute={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Expand Asset'));
    fireEvent.click(screen.getByLabelText(/Enable Mealie/i));

    expect(screen.getByRole('button', { name: /Execute & Sync/i })).toBeDisabled();
    expect(screen.getByText(/Preparing Service Data/i)).toBeInTheDocument();
  });

  it('Feature: asset-card-homebox-edit-fields | updates homebox fields and submits edited overrides', () => {
    const handleExecute = vi.fn();
    render(
      <AssetCard
        item={{ ...mockItem, selected_services: ['homebox'], ai_output: { llm_output: { product_name: 'Lamp', brand: 'BrightCo' } } }}
        onPreview={vi.fn()}
        onExecute={handleExecute}
      />,
    );

    fireEvent.click(screen.getByLabelText('Expand Asset'));
    fireEvent.click(screen.getByLabelText(/Expand Homebox details/i));

    fireEvent.change(screen.getByLabelText(/Location/i), { target: { value: 'Garage Shelf' } });
    fireEvent.change(screen.getByLabelText(/Quantity/i), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText(/Model Number/i), { target: { value: 'LMP-100' } });
    fireEvent.change(screen.getByLabelText(/Homebox Notes/i), { target: { value: 'Keep upright' } });

    fireEvent.click(screen.getByRole('button', { name: /Execute & Sync/i }));

    expect(handleExecute).toHaveBeenCalledWith(
      ['homebox'],
      expect.objectContaining({
        location: 'Garage Shelf',
        quantity: '2',
        model_number: 'LMP-100',
        notes: 'Keep upright',
      }),
    );
  });

  it('Feature: asset-card-mealie-edit-fields | updates recipe fields and submits edited payload', () => {
    const handleExecute = vi.fn();
    render(
      <AssetCard
        item={{ ...mockItem, selected_services: ['mealie'], ai_output: { llm_output: { product_name: 'Pancakes' } } }}
        onPreview={vi.fn()}
        onExecute={handleExecute}
      />,
    );

    fireEvent.click(screen.getByLabelText('Expand Asset'));
    fireEvent.click(screen.getByLabelText(/Expand Mealie details/i));

    fireEvent.change(screen.getByLabelText(/Yield/i), { target: { value: '4 servings' } });
    fireEvent.change(screen.getByLabelText(/Prep Time/i), { target: { value: '10 min' } });
    fireEvent.change(screen.getByLabelText(/Ingredients \(one per line\)/i), { target: { value: 'Flour\nEggs' } });
    fireEvent.change(screen.getByLabelText(/Tags \(comma separated\)/i), { target: { value: 'breakfast,quick' } });

    fireEvent.click(screen.getByRole('button', { name: /Execute & Sync/i }));

    expect(handleExecute).toHaveBeenCalledWith(
      ['mealie'],
      expect.objectContaining({
        yield: '4 servings',
        prep_time: '10 min',
        recipe_ingredients_raw: 'Flour\nEggs',
        tags: 'breakfast,quick',
      }),
    );
  });

  it('Feature: asset-card-changedetection-edit-fields | updates monitoring fields and submits edited payload', () => {
    const handleExecute = vi.fn();
    render(
      <AssetCard
        item={{ ...mockItem, selected_services: ['changedetection'], ai_output: { llm_output: { product_name: 'Widget' } } }}
        onPreview={vi.fn()}
        onExecute={handleExecute}
      />,
    );

    fireEvent.click(screen.getByLabelText('Expand Asset'));
    fireEvent.click(screen.getByLabelText(/Expand CD.io details/i));

    fireEvent.change(screen.getByLabelText(/Product URL/i), { target: { value: 'https://shop/widget' } });
    fireEvent.change(screen.getByLabelText(/^Tag$/i), { target: { value: 'Monitoring' } });
    fireEvent.change(screen.getByLabelText(/Check Every \(hours\)/i), { target: { value: '6' } });

    fireEvent.click(screen.getByRole('button', { name: /Execute & Sync/i }));

    expect(handleExecute).toHaveBeenCalledWith(
      ['changedetection'],
      expect.objectContaining({
        product_url: 'https://shop/widget',
        category: 'Monitoring',
        check_every_hours: '6',
      }),
    );
  });

  it('Feature: asset-card-service-generation-exception | enters error state when service generation throws and recovers on retry', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const generation = vi
      .fn()
      .mockRejectedValueOnce(new Error('request failed'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, output: { status: 'ready', data: { retailer: 'Retry Store' } } }),
      });

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/service-output/generate') {
        return (await generation()) as Response;
      }
      return { ok: true, json: async () => ({ logs: [] }) } as Response;
    });

    render(<AssetCard item={{ ...mockItem, selected_services: [] }} onPreview={vi.fn()} onExecute={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Expand Asset'));
    fireEvent.click(screen.getByLabelText(/Enable Price/i));

    await waitFor(() => {
      expect(screen.getByText(/Service generation failed/i)).toBeInTheDocument();
    });
    expect(errSpy).toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /Retry Service Run/i }));
    await waitFor(() => {
      expect(screen.getByLabelText(/Expand Price details/i)).toBeEnabled();
    });

    errSpy.mockRestore();
  });

  it('Feature: asset-card-collapse-visibility | renders expand button only when service checkbox is active', () => {
    render(<AssetCard item={mockItem} onPreview={vi.fn()} onExecute={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Expand Asset'));

    // Homebox is active, so its expand button should be visible
    expect(screen.getByLabelText(/Expand Homebox details/i)).toBeInTheDocument();

    // Mealie is not active, so its expand button should NOT be visible
    expect(screen.queryByLabelText(/Expand Mealie details/i)).not.toBeInTheDocument();
  });
});

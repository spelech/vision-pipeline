import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import App from '../App';

describe('Vision Pipeline App', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.startsWith('/api/queue')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            items: [
              {
                id: '1',
                image_path: 'test.jpg',
                status: 'pending',
                product_type: 'food',
                ai_output: {
                  llm_output: {
                    product_name: 'Test Product',
                    brand: 'Test Brand',
                    category: 'Test Category',
                    description: 'Test Description'
                  }
                },
                user_overrides: {},
                selected_services: ['homebox']
              }
            ]
          }),
        });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            success: true,
            pipelines: [{ id: 'default', name: 'Default Vision Pipeline' }],
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      });
    });
  });

  it('Feature: identify-shell | renders progress text and header', async () => {
    await act(async () => {
      render(<App />);
    });
    expect(screen.getByText(/Identify Asset/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Default Vision Pipeline/i).length).toBeGreaterThan(0);
  });

  it('Feature: review-navigation | fetches and displays the queue', async () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: /open menu/i }));
    fireEvent.click(screen.getByRole('button', { name: /^review$/i }));
    
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/queue?status=all');
    });

    expect(screen.getByText(/Review Queue/i)).toBeInTheDocument();
  });

  it('Feature: review-empty-state | shows empty state when queue is empty', async () => {
    // Override mock for empty queue
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.startsWith('/api/queue')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ items: [] }),
        });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ success: true, pipelines: [] }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({}),
      });
    });

    await act(async () => {
      render(<App />);
    });

    fireEvent.click(screen.getByRole('button', { name: /open menu/i }));
    fireEvent.click(screen.getByRole('button', { name: /^review$/i }));

    const emptyMsg = await screen.findByText(/Waiting for assets to ingest/i);
    expect(emptyMsg).toBeInTheDocument();
  });

  it('Feature: review-filters | changes queue filter from review controls', async () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: /open menu/i }));
    fireEvent.click(screen.getByRole('button', { name: /^review$/i }));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/queue?status=all');
    });

    fireEvent.click(screen.getByRole('button', { name: /Awaiting Review/i }));
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/queue?status=pending');
    });

    fireEvent.click(screen.getByRole('button', { name: /Approved/i }));
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/queue?status=approved');
    });
  });

  it('Feature: identify-upload-single | uploads a single file and fetches item details', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.startsWith('/api/queue')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ items: [] }),
        });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ success: true, pipelines: [{ id: 'default', name: 'Default Vision Pipeline' }] }),
        });
      }
      if (url === '/api/identify') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ success: true, item_id: '123' }),
        });
      }
      if (url === '/api/items/123') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: '123',
            image_path: 'masked_123.png',
            status: 'pending',
            product_type: 'food',
            ai_output: { llm_output: { product_name: 'Uploaded Product', brand: 'Uploaded Brand' } },
            user_overrides: {},
            selected_services: ['homebox'],
          }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    const { container } = render(<App />);

    const fileInputs = container.querySelectorAll('input[type="file"]');
    const identifyUploadInput = fileInputs[1] as HTMLInputElement;
    const file = new File(['abc'], 'single.jpg', { type: 'image/jpeg' });

    fireEvent.change(identifyUploadInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/identify', expect.objectContaining({ method: 'POST' }));
    });

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/items/123');
    });
  });

  it('Feature: batch-upload | uploads batch files in batch tab', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.startsWith('/api/queue')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ items: [] }),
        });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ success: true, pipelines: [{ id: 'default', name: 'Default Vision Pipeline' }] }),
        });
      }
      if (url === '/api/batch-upload') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ success: true, batch_id: 99 }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    const { container } = render(<App />);

    fireEvent.click(screen.getByRole('button', { name: /open menu/i }));
    fireEvent.click(screen.getByRole('button', { name: /^batch$/i }));

    const batchInput = container.querySelector('input[type="file"][multiple]') as HTMLInputElement;
    const files = [
      new File(['a'], 'batch-1.jpg', { type: 'image/jpeg' }),
      new File(['b'], 'batch-2.jpg', { type: 'image/jpeg' }),
    ];

    fireEvent.change(batchInput, { target: { files } });

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/batch-upload', expect.objectContaining({ method: 'POST' }));
    });
  });

  it('Feature: review-bulk-approve | approves selected pending items in bulk', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.startsWith('/api/queue')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            items: [
              {
                id: '1',
                image_path: 'pending.jpg',
                status: 'pending',
                product_type: 'food',
                ai_output: { llm_output: { product_name: 'Pending Item', brand: 'Brand' } },
                user_overrides: {},
                selected_services: ['homebox'],
              },
            ],
          }),
        });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ success: true, pipelines: [] }) });
      }
      if (url === '/api/bulk-approve') {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ success: [1], failed: [] }) });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: /open menu/i }));
    fireEvent.click(screen.getByRole('button', { name: /^review$/i }));
    fireEvent.click(screen.getByRole('button', { name: /Awaiting Review/i }));

    await waitFor(() => {
      expect(screen.getByText(/Select All/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Select All/i));

    const approveBtn = await screen.findByRole('button', { name: /Approve 1 Items/i });
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/bulk-approve', expect.objectContaining({ method: 'POST' }));
    });
  });

  it('Feature: camera-open-close | opens camera modal and closes it cleanly', async () => {
    const stopTrack = vi.fn();
    const fakeStream = { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream;
    const playSpy = vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue();

    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn().mockResolvedValue(fakeStream) },
    });

    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: /Open Camera/i }));

    await waitFor(() => {
      expect(screen.getByText(/Camera Capture/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));

    await waitFor(() => {
      expect(stopTrack).toHaveBeenCalled();
    });

    playSpy.mockRestore();
  });

  it('Feature: pipeline-fallback | falls back to default pipeline option when pipeline fetch fails', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.startsWith('/api/queue')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ items: [] }) });
      }
      if (url === '/api/pipelines') {
        return Promise.reject(new Error('pipelines unavailable'));
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getAllByText(/Default Vision Pipeline/i).length).toBeGreaterThan(0);
    });
  });

  it('Feature: identify-upload-failure | handles failed identify upload response', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.startsWith('/api/queue')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ items: [] }) });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ success: true, pipelines: [] }) });
      }
      if (url === '/api/identify') {
        return Promise.resolve({ ok: false, status: 500, json: async () => ({ success: false }) });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    const { container } = render(<App />);
    const identifyUploadInput = container.querySelectorAll('input[type="file"]')[1] as HTMLInputElement;
    fireEvent.change(identifyUploadInput, { target: { files: [new File(['abc'], 'single.jpg', { type: 'image/jpeg' })] } });

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/identify', expect.objectContaining({ method: 'POST' }));
    });
  });

  it('Feature: camera-fallback-input | falls back to capture input when camera access fails', async () => {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn().mockRejectedValue(new Error('denied')) },
    });

    const { container } = render(<App />);
    const captureInput = container.querySelector('input[capture="environment"]') as HTMLInputElement;
    const clickSpy = vi.spyOn(captureInput, 'click').mockImplementation(() => {});

    fireEvent.click(screen.getByRole('button', { name: /Open Camera/i }));

    await waitFor(() => {
      expect(clickSpy).toHaveBeenCalled();
    });

    clickSpy.mockRestore();
  });

  it('Feature: camera-capture-not-ready | shows readiness error when capture is attempted too early', async () => {
    const fakeStream = { getTracks: () => [{ stop: vi.fn() }] } as unknown as MediaStream;
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue();

    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn().mockResolvedValue(fakeStream) },
    });

    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: /Open Camera/i }));

    await screen.findByText(/Camera Capture/i);
    fireEvent.click(screen.getByRole('button', { name: /Capture and Process/i }));

    expect(await screen.findByText(/Camera preview is not ready yet/i)).toBeInTheDocument();
  });

  it('Feature: batch-upload-failure | shows error toast when batch upload request fails', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.startsWith('/api/queue')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ items: [] }) });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ success: true, pipelines: [] }) });
      }
      if (url === '/api/batch-upload') {
        return Promise.resolve({ ok: false, status: 500, json: async () => ({ success: false }) });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    const { container } = render(<App />);
    fireEvent.click(screen.getByRole('button', { name: /open menu/i }));
    fireEvent.click(screen.getByRole('button', { name: /^batch$/i }));

    const batchInput = container.querySelector('input[type="file"][multiple]') as HTMLInputElement;
    fireEvent.change(batchInput, {
      target: {
        files: [new File(['1'], 'a.jpg', { type: 'image/jpeg' }), new File(['2'], 'b.jpg', { type: 'image/jpeg' })],
      },
    });

    expect(await screen.findByText(/Batch upload failed/i)).toBeInTheDocument();
  });

  it('Feature: camera-no-media-devices-fallback | uses capture file input when media devices are unavailable', async () => {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: undefined,
    });

    const { container } = render(<App />);
    const captureInput = container.querySelector('input[capture="environment"]') as HTMLInputElement;
    const clickSpy = vi.spyOn(captureInput, 'click').mockImplementation(() => {});

    fireEvent.click(screen.getByRole('button', { name: /Open Camera/i }));

    await waitFor(() => {
      expect(clickSpy).toHaveBeenCalled();
    });

    clickSpy.mockRestore();
  });

  it('Feature: review-bulk-approve-error | surfaces error toast when bulk approve endpoint returns non-OK', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.startsWith('/api/queue')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            items: [{
              id: '1',
              image_path: 'pending.jpg',
              status: 'pending',
              product_type: 'food',
              ai_output: { llm_output: { product_name: 'Pending Item', brand: 'Brand' } },
              user_overrides: {},
              selected_services: ['homebox'],
            }],
          }),
        });
      }
      if (url === '/api/pipelines') {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ success: true, pipelines: [] }) });
      }
      if (url === '/api/bulk-approve') {
        return Promise.resolve({ ok: false, status: 500, json: async () => ({ success: false }) });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: /open menu/i }));
    fireEvent.click(screen.getByRole('button', { name: /^review$/i }));
    fireEvent.click(screen.getByRole('button', { name: /Awaiting Review/i }));
    fireEvent.click(await screen.findByText(/Select All/i));
    fireEvent.click(await screen.findByRole('button', { name: /Approve 1 Items/i }));

    expect(await screen.findByText(/Bulk approval failed/i)).toBeInTheDocument();
  });

});


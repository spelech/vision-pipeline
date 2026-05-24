import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import App from '../App';

describe('Vision Pipeline App', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/queue') {
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
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      });
    });
  });

  it('renders progress text and header', async () => {
    await act(async () => {
      render(<App />);
    });
    expect(screen.getByText(/Review Queue/i)).toBeInTheDocument();
  });

  it('fetches and displays the queue', async () => {
    render(<App />);
    
    await waitFor(() => {
      expect(screen.getByText('Test Product')).toBeInTheDocument();
    });
  });

  it('shows empty state when queue is empty', async () => {
    // Override mock for empty queue
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/queue') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ items: [] }),
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
    const emptyMsg = await screen.findByText(/Waiting for assets to ingest/i);
    expect(emptyMsg).toBeInTheDocument();
  });
});


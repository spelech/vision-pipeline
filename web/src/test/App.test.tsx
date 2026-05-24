import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import App from '../App';

describe('Vision Pipeline App', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    
    // @ts-expect-error - mocking global fetch
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/queue') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            items: [
              {
                id: '1',
                filename: 'test.jpg',
                thumbnail: 'test_thumb.jpg',
                timestamp: new Date().toISOString(),
                edit_data: {
                  product_name: 'Test Product',
                  brand: 'Test Brand',
                  category: 'Test Category',
                  description: 'Test Description'
                },
                product_type: 'food'
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

  it('renders progress text and header', () => {
    render(<App />);
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
    // @ts-expect-error - mocking global fetch
    global.fetch.mockImplementationOnce(() => 
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({ items: [] }),
      })
    );

    render(<App />);
    const emptyMsg = await screen.findByText(/Waiting for assets to ingest/i);
    expect(emptyMsg).toBeInTheDocument();
  });
});


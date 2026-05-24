import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import App from '../App';

describe('Vision Pipeline App', () => {
  it('renders progress text and header', () => {
    render(<App />);
    expect(screen.getByText(/Review Queue/i)).toBeInTheDocument();
  });

  it('shows empty state when queue is empty', async () => {
    // Mock fetch for empty queue
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });

    render(<App />);
    const emptyMsg = await screen.findByText(/Waiting for assets/i);
    expect(emptyMsg).toBeInTheDocument();
  });
});

import { render, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { NetworkCheck } from '../components/NetworkCheck';

describe('NetworkCheck', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('Feature: network-check-success | logs success when backend responds OK', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

    render(<NetworkCheck />);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/config');
      expect(logSpy).toHaveBeenCalledWith('Connection check successful');
    });
  });

  it('Feature: network-check-non-ok | logs error with status when backend returns non-OK', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 503 });
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(<NetworkCheck />);

    await waitFor(() => {
      expect(errSpy).toHaveBeenCalledWith('Connection check failed with status:', 503);
    });
  });

  it('Feature: network-check-rejection | logs error when request rejects', async () => {
    const rejected = new Error('offline');
    globalThis.fetch = vi.fn().mockRejectedValue(rejected);
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(<NetworkCheck />);

    await waitFor(() => {
      expect(errSpy).toHaveBeenCalledWith('Connection check failed completely:', rejected);
    });
  });
});

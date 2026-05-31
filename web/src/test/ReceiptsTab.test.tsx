import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ReceiptsTab } from '../app/ReceiptsTab';

describe('ReceiptsTab', () => {
  it('Feature: receipts-status-load | loads and displays gmail status on mount', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(JSON.stringify({
        oauth_configured: true,
        connected: true,
        receipt_wrangler_configured: false,
        processed_message_count: 3,
      })),
    });

    const onToast = vi.fn();
    render(<ReceiptsTab onToast={onToast} />);

    await screen.findByText('Configured');
    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('Feature: receipts-search-and-ingest | searches gmail receipts and ingests selected items', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({ oauth_configured: true, connected: true })),
      })
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({
          messages: [
            { message_id: 'm1', subject: 'Receipt 1', from: 'a@b.com', sent_at: '2026-05-01T00:00:00Z', has_attachments: true },
            { message_id: 'm2', subject: 'Receipt 2', from: 'c@d.com', sent_at: '2026-05-02T00:00:00Z', has_attachments: false },
          ],
        })),
      })
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({ success: true })),
      })
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({ oauth_configured: true, connected: true })),
      });

    const onToast = vi.fn();
    render(<ReceiptsTab onToast={onToast} />);

    await screen.findByText('Connected');

    fireEvent.click(screen.getByText('Search Gmail'));
    await screen.findByText('Receipt 1');
    await screen.findByText('Receipt 2');

    fireEvent.click(screen.getByText('Select All'));
    fireEvent.click(screen.getByText('Ingest Selected Direct'));

    await waitFor(() => {
      expect(onToast).toHaveBeenCalledWith('Direct ingestion started', 'success');
    });
  });

  it('Feature: receipts-selection-guard | informs user when action is attempted without selected messages', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(JSON.stringify({ oauth_configured: false })),
    });

    const onToast = vi.fn();
    render(<ReceiptsTab onToast={onToast} />);

    await screen.findByText('Not connected');
    fireEvent.click(screen.getByText('Mark Selected Processed'));

    expect(onToast).toHaveBeenCalledWith('Select at least one receipt first', 'info');
  });

  it('Feature: receipts-action-error | surfaces API detail when selected action fails', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({ oauth_configured: true, connected: true })),
      })
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({
          messages: [
            { message_id: 'm1', subject: 'Receipt 1', from: 'a@b.com', sent_at: '2026-05-01T00:00:00Z', has_attachments: true },
          ],
        })),
      })
      .mockResolvedValueOnce({
        ok: false,
        text: () => Promise.resolve(JSON.stringify({ detail: 'Receipt Wrangler is not configured' })),
      });

    const onToast = vi.fn();
    render(<ReceiptsTab onToast={onToast} />);

    await screen.findByText('Connected');
    fireEvent.click(screen.getByText('Search Gmail'));
    await screen.findByText('Receipt 1');

    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByText('Sync Selected to Receipt Wrangler'));

    await waitFor(() => {
      expect(onToast).toHaveBeenCalledWith('Receipt Wrangler is not configured', 'error');
    });
  });

  it('Feature: receipts-status-error | shows toast when status refresh fails', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('network'));

    const onToast = vi.fn();
    render(<ReceiptsTab onToast={onToast} />);

    await waitFor(() => {
      expect(onToast).toHaveBeenCalledWith('Failed to load Gmail status', 'error');
    });
  });

  it('Feature: receipts-select-all-toggle | toggles between selecting and clearing all receipts', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({ oauth_configured: true, connected: true })),
      })
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({
          messages: [
            { message_id: 'm1', subject: 'Receipt 1' },
            { message_id: 'm2', subject: 'Receipt 2' },
          ],
        })),
      });

    const onToast = vi.fn();
    render(<ReceiptsTab onToast={onToast} />);

    await screen.findByText('Connected');
    fireEvent.click(screen.getByText('Search Gmail'));
    await screen.findByText('Receipt 1');

    fireEvent.click(screen.getByText('Select All'));
    expect(screen.getByText('Selected: 2')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Unselect All'));
    expect(screen.getByText('Selected: 0')).toBeInTheDocument();
  });

  it('Feature: receipts-non-json-status | safely handles non-json status payloads', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve('not-json'),
    });

    const onToast = vi.fn();
    render(<ReceiptsTab onToast={onToast} />);

    await screen.findByText('Not connected');
    expect(onToast).not.toHaveBeenCalledWith('Failed to load Gmail status', 'error');
  });

  it('Feature: receipts-action-network-error | shows generic error when action request throws', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({ oauth_configured: true, connected: true })),
      })
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({
          messages: [{ message_id: 'm1', subject: 'Receipt 1' }],
        })),
      })
      .mockRejectedValueOnce(new Error('timeout'));

    const onToast = vi.fn();
    render(<ReceiptsTab onToast={onToast} />);

    await screen.findByText('Connected');
    fireEvent.click(screen.getByText('Search Gmail'));
    await screen.findByText('Receipt 1');

    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByText('Mark Selected Processed'));

    await waitFor(() => {
      expect(onToast).toHaveBeenCalledWith('Action failed', 'error');
    });
  });

  it('Feature: receipts-rw-process-pending | processes pending receipt wrangler receipts', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({ oauth_configured: true, connected: true })),
      })
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({ processed_count: 3 })),
      })
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({ oauth_configured: true, connected: true })),
      });

    const onToast = vi.fn();
    render(<ReceiptsTab onToast={onToast} />);

    await screen.findByText('Connected');
    fireEvent.click(screen.getByText('Process Pending RW Receipts'));

    await waitFor(() => {
      expect(onToast).toHaveBeenCalledWith('Processed 3 pending Receipt Wrangler receipts', 'success');
    });
  });

  it('Feature: receipts-rw-process-error | surfaces API detail when pending processing fails', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({ oauth_configured: true, connected: true })),
      })
      .mockResolvedValueOnce({
        ok: false,
        text: () => Promise.resolve(JSON.stringify({ detail: 'Receipt Wrangler is not configured' })),
      });

    const onToast = vi.fn();
    render(<ReceiptsTab onToast={onToast} />);

    await screen.findByText('Connected');
    fireEvent.click(screen.getByText('Process Pending RW Receipts'));

    await waitFor(() => {
      expect(onToast).toHaveBeenCalledWith('Receipt Wrangler is not configured', 'error');
    });
  });

  it('Feature: receipts-rw-process-network-error | shows generic error when pending processing request throws', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        text: () => Promise.resolve(JSON.stringify({ oauth_configured: true, connected: true })),
      })
      .mockRejectedValueOnce(new Error('network down'));

    const onToast = vi.fn();
    render(<ReceiptsTab onToast={onToast} />);

    await screen.findByText('Connected');
    fireEvent.click(screen.getByText('Process Pending RW Receipts'));

    await waitFor(() => {
      expect(onToast).toHaveBeenCalledWith('Action failed', 'error');
    });
  });
});

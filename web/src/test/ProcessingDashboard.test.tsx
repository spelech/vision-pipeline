import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ProcessingDashboard } from '../app/ProcessingDashboard';

describe('ProcessingDashboard', () => {
  it('Feature: processing-dashboard-empty | returns null when no processing file', () => {
    const { container } = render(
      <ProcessingDashboard
        processingFile={null}
        processingFileUrl=""
        processingSessionId={null}
        processingLogs={[]}
        processingError={null}
        onDismissError={vi.fn()}
      />,
    );

    expect(container.firstChild).toBeNull();
  });

  it('Feature: processing-dashboard-stages-and-logs | renders active completed pending and log styles', () => {
    const file = new File(['x'], 'upload.png', { type: 'image/png' });

    render(
      <ProcessingDashboard
        processingFile={file}
        processingFileUrl="blob://upload"
        processingSessionId="sess-123"
        processingLogs={[
          '[Node: Barcode] read',
          '[Node: Vision] started',
          '[Node: Search] completed',
          '[Node: Refine] completed',
          '✨ enriched payload',
          '🏁 finished',
        ]}
        processingError={null}
        onDismissError={vi.fn()}
      />,
    );

    expect(screen.getByAltText('Processing preview')).toBeInTheDocument();
    expect(screen.getByText(/ID: sess-123/i)).toBeInTheDocument();
    expect(screen.getByText(/Pipeline Processing/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Completed/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Processing/i)).toBeInTheDocument();
    expect(screen.getByText(/🏁 finished/i)).toBeInTheDocument();
  });

  it('Feature: processing-dashboard-error | shows dismiss controls and error message', () => {
    const onDismissError = vi.fn();
    const file = new File(['x'], 'upload.png', { type: 'image/png' });

    render(
      <ProcessingDashboard
        processingFile={file}
        processingFileUrl=""
        processingSessionId={null}
        processingLogs={['⚠️ failed to parse']}
        processingError="Pipeline exploded"
        onDismissError={onDismissError}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Dismiss Error/i }));

    expect(onDismissError).toHaveBeenCalled();
    expect(screen.getByText(/Error: Pipeline exploded/i)).toBeInTheDocument();
  });
});

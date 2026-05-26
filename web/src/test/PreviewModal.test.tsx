import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { PreviewModal } from '../components/PreviewModal';
import type { Asset } from '../types';

describe('PreviewModal', () => {
  const mockPreview = {
    item: {
      id: '1',
      image_path: 'test.jpg',
      status: 'pending',
      product_type: 'food',
      ai_output: {},
      selected_services: [],
    } as Asset,
    service: 'homebox',
    payload: { test_key: 'test_value' }
  };

  it('Feature: preview-modal-render | renders correctly and shows payload', () => {
    render(<PreviewModal preview={mockPreview} onClose={vi.fn()} onConfirm={vi.fn()} />);
    expect(screen.getByText('Pre-flight Review')).toBeInTheDocument();
    expect(screen.getByText('homebox')).toBeInTheDocument();
    expect(screen.getByDisplayValue(/test_key/)).toBeInTheDocument();
  });

  it('Feature: preview-modal-close | calls onClose when close button clicked', () => {
    const handleClose = vi.fn();
    render(<PreviewModal preview={mockPreview} onClose={handleClose} onConfirm={vi.fn()} />);
    
    fireEvent.click(screen.getByText('Cancel'));
    expect(handleClose).toHaveBeenCalled();
  });

  it('Feature: preview-modal-confirm | allows payload editing and confirms', () => {
    const handleConfirm = vi.fn();
    render(<PreviewModal preview={mockPreview} onClose={vi.fn()} onConfirm={handleConfirm} />);
    
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: '{"test_key": "new_value"}' } });

    fireEvent.click(screen.getByText(/Confirm & Transmit to/));
    expect(handleConfirm).toHaveBeenCalledWith({ test_key: 'new_value' });
  });
});

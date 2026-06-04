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
    payload: { name: 'Test Item', quantity: 2, location: 'Kitchen' }
  };

  it('Feature: preview-modal-render | renders Form Review by default', () => {
    render(<PreviewModal preview={mockPreview} onClose={vi.fn()} onConfirm={vi.fn()} />);
    expect(screen.getByText('Pre-flight Review')).toBeInTheDocument();
    expect(screen.getByText('homebox')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Test Item')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Kitchen')).toBeInTheDocument();
  });

  it('Feature: preview-modal-close | calls onClose when close button clicked', () => {
    const handleClose = vi.fn();
    render(<PreviewModal preview={mockPreview} onClose={handleClose} onConfirm={vi.fn()} />);
    
    fireEvent.click(screen.getByText('Cancel'));
    expect(handleClose).toHaveBeenCalled();
  });

  it('Feature: preview-modal-close-icon | calls onClose when header close icon clicked', () => {
    const handleClose = vi.fn();
    const { container } = render(<PreviewModal preview={mockPreview} onClose={handleClose} onConfirm={vi.fn()} />);

    const closeIconButton = container.querySelector('div.p-6 button') as HTMLButtonElement;
    fireEvent.click(closeIconButton);
    expect(handleClose).toHaveBeenCalled();
  });

  it('Feature: preview-modal-confirm-form | submits form overrides directly', () => {
    const handleConfirm = vi.fn();
    render(<PreviewModal preview={mockPreview} onClose={vi.fn()} onConfirm={handleConfirm} />);
    
    const nameInput = screen.getByDisplayValue('Test Item');
    fireEvent.change(nameInput, { target: { value: 'New Test Name' } });

    fireEvent.click(screen.getByText(/Confirm & Transmit to/));
    expect(handleConfirm).toHaveBeenCalledWith(expect.objectContaining({ name: 'New Test Name', quantity: 2 }));
  });

  it('Feature: preview-modal-json-toggle | allows switching to JSON and editing raw text', () => {
    const handleConfirm = vi.fn();
    render(<PreviewModal preview={mockPreview} onClose={vi.fn()} onConfirm={handleConfirm} />);

    // Toggle Raw JSON view
    fireEvent.click(screen.getByText('Raw JSON'));
    
    const textarea = screen.getByRole('textbox');
    expect(textarea).toBeInTheDocument();
    expect(textarea.innerHTML).toContain('Test Item');

    fireEvent.change(textarea, { target: { value: '{"name": "JSON Edit", "quantity": 10}' } });
    fireEvent.click(screen.getByText(/Confirm & Transmit to/));
    expect(handleConfirm).toHaveBeenCalledWith({ name: 'JSON Edit', quantity: 10 });
  });

  it('Feature: preview-modal-invalid-json | shows error on bad JSON and blocks confirm', () => {
    const handleConfirm = vi.fn();
    render(<PreviewModal preview={mockPreview} onClose={vi.fn()} onConfirm={handleConfirm} />);

    // Switch to Raw JSON view
    fireEvent.click(screen.getByText('Raw JSON'));
    
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: '{bad json' } });
    fireEvent.click(screen.getByText(/Confirm & Transmit to/));

    expect(screen.getByText(/Invalid JSON format/i)).toBeInTheDocument();
    expect(handleConfirm).not.toHaveBeenCalled();

    // Fix JSON
    fireEvent.change(textarea, { target: { value: '{"name": "Fixed"}' } });
    expect(screen.queryByText(/Invalid JSON format/i)).not.toBeInTheDocument();
  });
});

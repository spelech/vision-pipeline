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

  it('Feature: preview-modal-mealie | renders and submits Mealie recipe form', () => {
    const handleConfirm = vi.fn();
    const mealiePreview = {
      item: mockPreview.item,
      service: 'mealie',
      payload: {
        name: 'Chocolate Cake',
        description: 'Yummy cake',
        recipeIngredients: [{ note: '1 cup sugar' }, { note: '2 cups flour' }],
        recipeInstructions: [{ text: 'Mix ingredients' }, { text: 'Bake it' }],
        yield: '8 servings'
      }
    };

    render(<PreviewModal preview={mealiePreview} onClose={vi.fn()} onConfirm={handleConfirm} />);
    
    expect(screen.getByText('Recipe Name')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Chocolate Cake')).toBeInTheDocument();
    expect(screen.getByDisplayValue('8 servings')).toBeInTheDocument();

    const ingredientsTextarea = screen.getByPlaceholderText(/2 cups of flour/i);
    fireEvent.change(ingredientsTextarea, { target: { value: "1 cup sugar\n2 cups flour\n1 tsp salt" } });

    const instructionsTextarea = screen.getByPlaceholderText(/Mix flour and /i);
    fireEvent.change(instructionsTextarea, { target: { value: "Mix ingredients\nBake it\nEnjoy" } });

    fireEvent.click(screen.getByText(/Confirm & Transmit to/));
    expect(handleConfirm).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Chocolate Cake',
      yield: '8 servings',
      recipeIngredients: [{ note: '1 cup sugar' }, { note: '2 cups flour' }, { note: '1 tsp salt' }],
      recipeInstructions: [{ text: 'Mix ingredients' }, { text: 'Bake it' }, { text: 'Enjoy' }]
    }));
  });

  it('Feature: preview-modal-pricebuddy | renders and submits PriceBuddy form', () => {
    const handleConfirm = vi.fn();
    const priceBuddyPreview = {
      item: mockPreview.item,
      service: 'pricebuddy',
      payload: {
        name: 'Desk Lamp',
        barcode: '1234567890',
        tags: ['pantry', 'grocery'],
        urls: ['https://amazon.com/item', 'https://walmart.com/item']
      }
    };

    render(<PreviewModal preview={priceBuddyPreview} onClose={vi.fn()} onConfirm={handleConfirm} />);

    expect(screen.getByText('Barcode')).toBeInTheDocument();
    expect(screen.getByDisplayValue('1234567890')).toBeInTheDocument();
    expect(screen.getByDisplayValue('pantry, grocery')).toBeInTheDocument();

    const urlsTextarea = screen.getByPlaceholderText(/e.g. https:\/\/amazon.com/i);
    fireEvent.change(urlsTextarea, { target: { value: "https://amazon.com/item\nhttps://walmart.com/item\nhttps://target.com/item" } });

    const tagsInput = screen.getByDisplayValue('pantry, grocery');
    fireEvent.change(tagsInput, { target: { value: 'pantry, grocery, lighting' } });

    fireEvent.click(screen.getByText(/Confirm & Transmit to/));
    expect(handleConfirm).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Desk Lamp',
      barcode: '1234567890',
      tags: ['pantry', 'grocery', 'lighting'],
      urls: ['https://amazon.com/item', 'https://walmart.com/item', 'https://target.com/item']
    }));
  });

  it('Feature: preview-modal-changedetection | renders and submits ChangeDetection form', () => {
    const handleConfirm = vi.fn();
    const changeDetectionPreview = {
      item: mockPreview.item,
      service: 'changedetection',
      payload: {
        title: 'Monitor Page',
        url: 'https://example.com/watch',
        tag: 'Tech'
      }
    };

    render(<PreviewModal preview={changeDetectionPreview} onClose={vi.fn()} onConfirm={handleConfirm} />);

    expect(screen.getByText('URL to Monitor')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Monitor Page')).toBeInTheDocument();
    expect(screen.getByDisplayValue('https://example.com/watch')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Tech')).toBeInTheDocument();

    const titleInput = screen.getByDisplayValue('Monitor Page');
    fireEvent.change(titleInput, { target: { value: 'Updated Monitor Page' } });

    fireEvent.click(screen.getByText(/Confirm & Transmit to/));
    expect(handleConfirm).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Updated Monitor Page',
      url: 'https://example.com/watch',
      tag: 'Tech'
    }));
  });

  it('Feature: preview-modal-generic | renders and submits generic form for unknown service', () => {
    const handleConfirm = vi.fn();
    const genericPreview = {
      item: mockPreview.item,
      service: 'unknown_service',
      payload: {
        some_string: 'val1',
        some_number: 123,
        some_bool: true,
        some_object: { nested: 'obj' } // should be ignored by renderGenericForm loop
      }
    };

    render(<PreviewModal preview={genericPreview} onClose={vi.fn()} onConfirm={handleConfirm} />);

    expect(screen.getByText(/No predefined form view for this service/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue('val1')).toBeInTheDocument();
    expect(screen.getByDisplayValue('123')).toBeInTheDocument();
    expect(screen.getByDisplayValue('true')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('nested')).not.toBeInTheDocument();

    const val1Input = screen.getByDisplayValue('val1');
    fireEvent.change(val1Input, { target: { value: 'val1_updated' } });

    fireEvent.click(screen.getByText(/Confirm & Transmit to/));
    expect(handleConfirm).toHaveBeenCalledWith(expect.objectContaining({
      some_string: 'val1_updated',
      some_number: 123,
      some_bool: true
    }));
  });
});


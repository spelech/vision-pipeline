import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AssetCard } from '../components/AssetCard';

describe('AssetCard', () => {
  const mockItem = {
    id: 1,
    filename: 'test-image.jpg',
    product_type: 'food',
    edit_data: { product_name: 'Test Food', brand: 'Test Brand', category: 'Snack', description: 'desc' },
    selected_services: ['homebox']
  };

  it('renders collapsed state correctly', () => {
    const { container } = render(<AssetCard item={mockItem} onPreview={vi.fn()} onExecute={vi.fn()} />);
    expect(screen.getByText('Test Food')).toBeInTheDocument();
    expect(screen.getByText('test-image.jpg')).toBeInTheDocument();
    expect(screen.getByText('food')).toBeInTheDocument();
    
    // Check that expanded fields are not visible
    expect(screen.queryByLabelText('Brand')).not.toBeInTheDocument();
  });

  it('expands when clicking the chevron', () => {
    render(<AssetCard item={mockItem} onPreview={vi.fn()} onExecute={vi.fn()} />);
    const expandBtn = screen.getByLabelText('Expand Asset');
    fireEvent.click(expandBtn);

    expect(screen.getByDisplayValue('Test Brand')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Snack')).toBeInTheDocument();
    expect(screen.getByDisplayValue('desc')).toBeInTheDocument();
  });

  it('updates edit data and fires onExecute with overrides', () => {
    const handleExecute = vi.fn();
    render(<AssetCard item={mockItem} onPreview={vi.fn()} onExecute={handleExecute} />);
    
    fireEvent.click(screen.getByLabelText('Expand Asset'));
    
    const brandInput = screen.getByDisplayValue('Test Brand');
    fireEvent.change(brandInput, { target: { value: 'New Brand' } });
    
    fireEvent.click(screen.getByText(/Execute & Sync/i));
    
    expect(handleExecute).toHaveBeenCalledWith(expect.objectContaining({ brand: 'New Brand', product_name: 'Test Food' }));
  });

  it('toggles selection', () => {
    const handleToggleSelect = vi.fn();
    const { container } = render(<AssetCard item={mockItem} isSelected={false} onToggleSelect={handleToggleSelect} onPreview={vi.fn()} onExecute={vi.fn()} />);
    
    // Since there's no aria-label, we can find it by className or click early element
    // It's the first div inside the p-6 div that handles toggle
    const toggleDiv = container.querySelector('.cursor-pointer');
    fireEvent.click(toggleDiv!);
    expect(handleToggleSelect).toHaveBeenCalled();
  });
});

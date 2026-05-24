export interface AssetEditData {
  product_name?: string;
  brand?: string;
  category?: string;
  description?: string;
  [key: string]: unknown;
}

export interface Asset {
  id: string;
  filename: string;
  original_filename: string;
  brand?: string;
  category?: string;
  description?: string;
  product_type: 'product' | 'food';
  edit_data: AssetEditData;
  selected_services: string[];
}

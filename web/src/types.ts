export interface AssetEditData {
  product_name?: string;
  brand?: string;
  category?: string;
  description?: string;
  price?: string;
  [key: string]: unknown;
}

export interface Asset {
  id: string;
  image_path: string;
  raw_image_path?: string;
  status: string;
  product_type: 'product' | 'food' | 'unknown';
  ai_output?: {
    llm_output?: Record<string, unknown>;
    vision_raw?: string;
    [key: string]: unknown;
  };
  user_overrides?: Record<string, unknown>;
  selected_services: string[];
}

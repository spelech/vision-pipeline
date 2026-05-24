export interface AssetEditData {
  product_name?: string;
  brand?: string;
  category?: string;
  description?: string;
  [key: string]: unknown;
}

export interface Asset {
  id: string;
  image_path: string;
  raw_image_path?: string;
  status: string;
  product_type: 'product' | 'food' | 'unknown';
  ai_output?: {
    llm_output?: Record<string, any>;
    vision_raw?: string;
    [key: string]: any;
  };
  user_overrides?: Record<string, any>;
  selected_services: string[];
}

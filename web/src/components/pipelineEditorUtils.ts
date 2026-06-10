export interface Pipeline {
  id: string;
  name: string;
  schema: {
    active_nodes?: { default: string[] };
    vision_model?: { default: string };
    custom_prompt?: { default: string };
    vision_prompt?: { default: string };
    refine_prompt?: { default: string };
    scrape_wait_time?: { default: number | string };
  };
}

export const DEFAULT_PIPELINE_MODELS = ['qwen3-vl-235b-a22b-instruct'];

export function getPipelineNodes(pipeline: Pipeline): string[] {
  if (Array.isArray(pipeline.schema.active_nodes?.default) && pipeline.schema.active_nodes.default.length > 0) {
    return pipeline.schema.active_nodes.default;
  }

  if (pipeline.id === 'advanced_playwright') {
    return ['barcode', 'vision', 'search', 'scrape', 'refine'];
  }

  return ['barcode', 'vision', 'search', 'refine'];
}

export function isPersistedCustomPipeline(pipeline: Pipeline): boolean {
  return pipeline.id === 'composable' || pipeline.id.startsWith('custom_');
}

export function getVisionPrompt(pipeline: Pipeline): string {
  return pipeline.schema.vision_prompt?.default || pipeline.schema.custom_prompt?.default || '';
}

export function getRefinePrompt(pipeline: Pipeline): string {
  return pipeline.schema.refine_prompt?.default || '';
}

export function getPromptPreview(prompt: string): string {
  const trimmed = prompt.trim();
  if (!trimmed) {
    return 'No prompt configured';
  }
  return trimmed.length > 90 ? `${trimmed.slice(0, 90)}...` : trimmed;
}

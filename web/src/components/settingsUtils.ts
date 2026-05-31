export interface PromptTemplate {
  id: string | number;
  name: string;
  prompt: string;
}

export interface PipelineApiResponse {
  success?: boolean;
  pipelines?: Array<{
    id: string;
    name: string;
    schema?: Record<string, { default?: unknown }>;
  }>;
}

export function normalizePromptTemplates(value: unknown): PromptTemplate[] {
  if (Array.isArray(value)) {
    return value
      .filter((template): template is PromptTemplate => typeof template === 'object' && template !== null && 'id' in template && 'name' in template && 'prompt' in template)
      .map((template) => ({
        id: template.id,
        name: template.name,
        prompt: template.prompt,
      }));
  }

  if (value && typeof value === 'object') {
    return Object.entries(value as Record<string, string>).map(([id, prompt]) => ({
      id,
      name: id.replace(/_/g, ' ').toUpperCase(),
      prompt: String(prompt),
    }));
  }

  return [];
}

export function derivePromptTemplatesFromPipelines(pipelines: PipelineApiResponse['pipelines']): PromptTemplate[] {
  if (!Array.isArray(pipelines)) {
    return [];
  }

  return pipelines.flatMap((pipeline) => {
    const schema = pipeline.schema || {};
    return Object.entries(schema)
      .filter(([key]) => key.includes('prompt'))
      .map(([key, definition]) => ({
        id: `${pipeline.id}-${key}`,
        name: `${pipeline.name} ${key.replace(/_/g, ' ')}`,
        prompt: typeof definition?.default === 'string' ? definition.default : '',
      }));
  });
}

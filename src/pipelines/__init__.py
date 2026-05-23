from .base import BasePipeline
from .default import DefaultPipeline
from .advanced import AdvancedPipeline
from .composable import ComposablePipeline

PIPELINE_REGISTRY = {
    DefaultPipeline.get_id(): DefaultPipeline,
    AdvancedPipeline.get_id(): AdvancedPipeline,
    ComposablePipeline.get_id(): ComposablePipeline
}

def get_pipeline(pipeline_id: str) -> BasePipeline:
    PipelineClass = PIPELINE_REGISTRY.get(pipeline_id, DefaultPipeline)
    return PipelineClass()

def get_all_pipelines():
    return [
        {
            "id": p_class.get_id(),
            "name": p_class.get_name(),
            "schema": p_class.get_settings_schema()
        }
        for p_class in PIPELINE_REGISTRY.values()
    ]

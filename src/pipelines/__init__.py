from .base import BasePipeline
from .default import DefaultPipeline
from .advanced import AdvancedPipeline
from .composable import ComposablePipeline
from .service_pipelines import (
    HomeboxServicePipeline,
    MealieServicePipeline,
    PriceBuddyServicePipeline,
    ChangeDetectionServicePipeline,
)

PIPELINE_REGISTRY = {
    DefaultPipeline.get_id(): DefaultPipeline,
    AdvancedPipeline.get_id(): AdvancedPipeline,
    ComposablePipeline.get_id(): ComposablePipeline,
    HomeboxServicePipeline.get_id(): HomeboxServicePipeline,
    MealieServicePipeline.get_id(): MealieServicePipeline,
    PriceBuddyServicePipeline.get_id(): PriceBuddyServicePipeline,
    ChangeDetectionServicePipeline.get_id(): ChangeDetectionServicePipeline,
}


def get_pipeline(pipeline_id: str) -> BasePipeline:
    pipeline_class = PIPELINE_REGISTRY.get(pipeline_id, DefaultPipeline)
    return pipeline_class()


def get_all_pipelines():
    return [
        {
            "id": p_class.get_id(),
            "name": p_class.get_name(),
            "schema": p_class.get_settings_schema()
        }
        for p_class in PIPELINE_REGISTRY.values()
    ]

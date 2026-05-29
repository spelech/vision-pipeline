from .composable import ComposablePipeline


class BaseServicePipeline(ComposablePipeline):
    pipeline_id = "service_base"
    pipeline_name = "Service Pipeline"
    default_nodes = ["barcode", "vision", "search", "refine"]

    @classmethod
    def get_id(cls) -> str:
        return cls.pipeline_id

    @classmethod
    def get_name(cls) -> str:
        return cls.pipeline_name

    @classmethod
    def get_settings_schema(cls) -> dict:
        schema = super().get_settings_schema()
        schema["active_nodes"]["default"] = list(cls.default_nodes)
        return schema


class HomeboxServicePipeline(BaseServicePipeline):
    pipeline_id = "service_homebox"
    pipeline_name = "Service Pipeline: Homebox"
    default_nodes = ["barcode", "vision", "search", "refine"]


class MealieServicePipeline(BaseServicePipeline):
    pipeline_id = "service_mealie"
    pipeline_name = "Service Pipeline: Mealie"
    default_nodes = ["barcode", "vision", "search", "scrape", "refine"]


class PriceBuddyServicePipeline(BaseServicePipeline):
    pipeline_id = "service_pricebuddy"
    pipeline_name = "Service Pipeline: PriceBuddy"
    default_nodes = ["barcode", "vision", "search", "refine"]


class ChangeDetectionServicePipeline(BaseServicePipeline):
    pipeline_id = "service_changedetection"
    pipeline_name = "Service Pipeline: ChangeDetection"
    default_nodes = ["vision", "search", "scrape", "refine"]

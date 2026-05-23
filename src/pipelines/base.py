class BasePipeline:
    """
    Abstract base class for all Vision Pipelines.
    """

    @classmethod
    def get_id(cls) -> str:
        raise NotImplementedError

    @classmethod
    def get_name(cls) -> str:
        raise NotImplementedError

    @classmethod
    def get_settings_schema(cls) -> dict:
        """
        Returns a JSON schema-like dictionary describing configurable settings.
        e.g., {"model": {"type": "string", "default": "qwen..."}, "prompt": {"type": "string"}}
        """
        return {}

    def run(self, image=None, text_description=None, settings=None, log_cb=None) -> dict:
        """
        Executes the pipeline and returns a standardized result dictionary:
        {
            "barcode": str | None,
            "llm_output": dict,
            "searxng_results": list
        }
        """
        raise NotImplementedError

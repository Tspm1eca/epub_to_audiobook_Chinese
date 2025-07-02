from typing import List

from audiobook_generator.config.general_config import GeneralConfig

TTS_AZURE = "azure"
TTS_OPENAI = "openai"
TTS_EDGE = "edge"
TTS_PIPER = 'piper'


class BaseTTSProvider:  # Base interface for TTS providers
    # Base provider interface
    def __init__(self, config: GeneralConfig):
        self.config = config

    def __str__(self) -> str:
        return f"{self.config}"

    def validate_config(self):
        raise NotImplementedError

    async def async_text_to_speech(self, *args, **kwargs):
        raise NotImplementedError

    def estimate_cost(self, total_chars):
        raise NotImplementedError

    def get_break_string(self):
        raise NotImplementedError

    def get_output_file_extension(self):
        raise NotImplementedError


# Common support methods for all TTS providers
def get_supported_tts_providers() -> List[str]:
    return [TTS_AZURE, TTS_OPENAI, TTS_EDGE, TTS_PIPER]


async def get_async_tts_provider(config) -> BaseTTSProvider:
    provider = None
    if config.tts == TTS_AZURE:
        from audiobook_generator.tts_providers.azure_tts_provider import AzureTTSProvider
        provider = AzureTTSProvider(config)
    elif config.tts == TTS_OPENAI:
        from audiobook_generator.tts_providers.openai_tts_provider import OpenAITTSProvider
        provider = OpenAITTSProvider(config)
    elif config.tts == TTS_EDGE:
        from audiobook_generator.tts_providers.edge_tts_provider import EdgeTTSProvider
        provider = EdgeTTSProvider(config)
    elif config.tts == TTS_PIPER:
        from audiobook_generator.tts_providers.piper_tts_provider import PiperTTSProvider
        provider = PiperTTSProvider(config)

    if provider:
        await provider.validate_config()
        return provider
    else:
        raise ValueError(f"Invalid TTS provider: {config.tts}")

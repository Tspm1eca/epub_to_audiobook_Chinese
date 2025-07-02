import io
import logging
import math
import asyncio
import aiofiles

from openai import OpenAI, AsyncOpenAI

from audiobook_generator.core.audio_tags import AudioTags
from audiobook_generator.config.general_config import GeneralConfig
from audiobook_generator.core.utils import split_text, set_audio_tags
from audiobook_generator.tts_providers.base_tts_provider import BaseTTSProvider


logger = logging.getLogger(__name__)


def get_supported_models():
    return ["tts-1", "tts-1-hd"]


def get_supported_voices():
    return ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


def get_supported_formats():
    return ["mp3", "aac", "flac", "opus"]


class OpenAITTSProvider(BaseTTSProvider):
    def __init__(self, config: GeneralConfig):
        logger.setLevel(config.log)
        config.model_name = config.model_name or "tts-1"
        config.voice_name = config.voice_name or "alloy"
        config.output_format = config.output_format or "mp3"

        # per 1000 characters (0.03$ for HD model, 0.015$ for standard model)
        self.price = 0.03 if config.model_name == "tts-1-hd" else 0.015
        super().__init__(config)

        self.client = OpenAI()  # User should set OPENAI_API_KEY environment variable
        self.async_client = AsyncOpenAI()

    def __str__(self) -> str:
        return super().__str__()

    async def async_text_to_speech(self, text: str, output_file: str, audio_tags: AudioTags):
        max_chars = 4000  # should be less than 4096 for OpenAI
        text_chunks = split_text(text, max_chars, self.config.language)

        async with aiofiles.open(output_file, "wb") as outfile:
            tasks = []
            for i, chunk in enumerate(text_chunks, 1):
                tasks.append(self.process_chunk(chunk, i, len(text_chunks), audio_tags))

            audio_segments = await asyncio.gather(*tasks)

            for segment in audio_segments:
                await outfile.write(segment)

        set_audio_tags(output_file, audio_tags)

    async def process_chunk(self, chunk: str, i: int, total_chunks: int, audio_tags: AudioTags) -> bytes:
        logger.info(
            f"Processing chapter-{audio_tags.idx} <{audio_tags.title}>, chunk {i} of {total_chunks}"
        )
        response = await self.async_client.audio.speech.create(
            model=self.config.model_name,
            voice=self.config.voice_name,
            input=chunk,
            response_format=self.config.output_format,
        )
        return response.content


    def get_break_string(self):
        return "   "

    def get_output_file_extension(self):
        return self.config.output_format

    def validate_config(self):
        if self.config.model_name not in get_supported_models():
            raise ValueError(f"OpenAI: Unsupported model name: {self.config.model_name}")
        if self.config.voice_name not in get_supported_voices():
            raise ValueError(f"OpenAI: Unsupported voice name: {self.config.voice_name}")
        if self.config.output_format not in get_supported_formats():
            raise ValueError(f"OpenAI: Unsupported output format: {self.config.output_format}")

    def estimate_cost(self, total_chars):
        return math.ceil(total_chars / 1000) * self.price

import asyncio
import logging
import math
import time
import aiofiles
import lameenc
import regex as re

from edge_tts import Communicate, list_voices

from audiobook_generator.config.general_config import GeneralConfig
from audiobook_generator.core.audio_tags import AudioTags
from audiobook_generator.core.utils import set_audio_tags
from audiobook_generator.tts_providers.base_tts_provider import BaseTTSProvider

logger = logging.getLogger(__name__)

MAX_RETRIES = 3  # Max_retries constant for network errors


async def get_supported_voices():
    # List all available voices and their attributes.
    # This pulls data from the URL used by Microsoft Edge to return a list of
    # all available voices.
    # Returns:
    #     dict: A dictionary of voice attributes.
    voices = await list_voices()
    voices = sorted(voices, key=lambda voice: voice["ShortName"])

    result = {}

    for voice in voices:
        result[voice["ShortName"]] = voice["Locale"]

    return result


class CommWithPauses:
    def __init__(
        self,
        text: str,
        voice_name: str,
        break_string: str,
        break_duration: int = 500,
        **kwargs,
    ) -> None:
        # @BRK# -> [pause=500]
        self.text = text.replace(break_string, f"[pause={break_duration}]")
        self.voice = voice_name
        self.volume = f"+{kwargs.get('volume', 0)}%"
        self.rate = f"+{kwargs.get('rate', 0)}%"
        self.pitch = f"+{kwargs.get('pitch', 0)}Hz"
        self.break_duration = break_duration

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.run_tts())

    async def process_segment(self, segment):
        if re.match(r'\[pause=\d+\]', segment):
            return await asyncio.to_thread(self.generate_silence)

        for i in range(MAX_RETRIES):
            try:
                communicate = Communicate(
                    segment, self.voice, rate=self.rate, volume=self.volume, pitch=self.pitch)

            except Exception:
                logger.error(f"[{i}] An error occurred retrying...")
                continue
            else:
                break

        segment_audio = b''.join([chunk["data"] async for chunk in communicate.stream() if chunk["type"] == "audio"])
        return segment_audio

    async def run_tts(self):
        segments = re.split(r'(\[pause=\d+\])', self.text)
        tasks = [self.process_segment(segment)
                 # \p{L}為任何文字字符（所有國家）
                 for segment in segments if re.search(r'\p{L}', segment)]
        results = await asyncio.gather(*tasks)
        self.combined_audio = b''.join(results)

    def generate_silence(self, sample_rate=24000, bit_depth=16):
        num_frames = int(sample_rate * self.break_duration / 1000)
        silent_frame = b'\x00' * (bit_depth // 8) * num_frames
        encoder = lameenc.Encoder()
        encoder.set_channels(1)
        encoder.set_in_sample_rate(sample_rate)
        encoder.set_bit_rate(128)
        encoder.set_out_sample_rate(sample_rate)
        encoder.set_quality(2)
        mp3_data = encoder.encode(silent_frame)
        mp3_data += encoder.flush()
        return mp3_data

    async def save(self, audio_fname) -> None:
        async with aiofiles.open(audio_fname, "wb") as f:
            await f.write(self.combined_audio)


class EdgeTTSProvider(BaseTTSProvider):
    def __init__(self, config: GeneralConfig):
        logger.setLevel(config.log)
        # TTS provider specific config
        config.voice_name = config.voice_name or "en-US-GuyNeural"
        config.output_format = config.output_format or "audio-24khz-48kbitrate-mono-mp3"
        config.voice_rate = config.voice_rate or 0
        config.voice_volume = config.voice_volume or 0
        config.voice_pitch = config.voice_pitch or 0
        config.proxy = config.proxy or None

        # 0.000$ per 1 million characters
        # or 0.000$ per 1000 characters
        self.price = 0.000
        super().__init__(config)

    def __str__(self) -> str:
        return f"{self.config}"

    def validate_config(self):
        supported_voices = asyncio.run(get_supported_voices())
        # logger.debug(f"Supported voices: {supported_voices}")
        if self.config.voice_name not in supported_voices:
            raise ValueError(
                f"EdgeTTS: Unsupported voice name: {self.config.voice_name}")

    def text_to_speech(
            self,
            text: str,
            output_file: str,
            audio_tags: AudioTags,
    ):

        start = time.time()
        communicate = CommWithPauses(
            text=text,
            voice_name=self.config.voice_name,
            break_string=self.get_break_string().strip(),
            break_duration=int(self.config.break_duration),
            rate=self.config.voice_rate,
            volume=self.config.voice_volume,
            pitch=self.config.voice_pitch,
            proxy=self.config.proxy,
        )

        asyncio.run(communicate.save(output_file))

        set_audio_tags(output_file, audio_tags)
        logger.info(f"Proceed Time: {round(time.time() - start, 2)}s")

    def estimate_cost(self, total_chars):
        return math.ceil(total_chars / 1000) * self.price

    def get_break_string(self):
        return " @BRK#"

    def get_output_file_extension(self):
        if self.config.output_format.endswith("mp3"):
            return "mp3"
        else:
            # Only mp3 supported in edge-tts https://github.com/rany2/edge-tts/issues/179
            raise NotImplementedError(
                f"Unknown file extension for output format: {self.config.output_format}. Only mp3 supported in edge-tts. See https: // github.com/rany2/edge-tts/issues/179."
            )

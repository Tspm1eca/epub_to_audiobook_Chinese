import html
import io
import logging
import math
import os
from datetime import datetime, timedelta
from time import sleep
import requests
import asyncio
import aiohttp
import aiofiles

from audiobook_generator.core.audio_tags import AudioTags
from audiobook_generator.config.general_config import GeneralConfig
from audiobook_generator.core.utils import split_text, set_audio_tags
from audiobook_generator.tts_providers.base_tts_provider import BaseTTSProvider

logger = logging.getLogger(__name__)

MAX_RETRIES = 12  # Max_retries constant for network errors


class AzureTTSProvider(BaseTTSProvider):
    def __init__(self, config: GeneralConfig):
        logger.setLevel(config.log)
        # TTS provider specific config
        config.voice_name = config.voice_name or "en-US-GuyNeural"
        config.output_format = config.output_format or "audio-24khz-48kbitrate-mono-mp3"

        # 16$ per 1 million characters
        # or 0.016$ per 1000 characters
        self.price = 0.016
        # access token and expiry time
        self.access_token = None
        self.token_expiry_time = datetime.utcnow()
        super().__init__(config)

        subscription_key = os.environ.get("MS_TTS_KEY")
        region = os.environ.get("MS_TTS_REGION")

        if not subscription_key or not region:
            raise ValueError(
                "Please set MS_TTS_KEY and MS_TTS_REGION environment variables. Check https://github.com/p0n1/epub_to_audiobook#how-to-get-your-azure-cognitive-service-key."
            )

        self.TOKEN_URL = (
            f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issuetoken"
        )
        self.TOKEN_HEADERS = {"Ocp-Apim-Subscription-Key": subscription_key}
        self.TTS_URL = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"

    def __str__(self) -> str:
        return (
                super().__str__()
                + f", voice_name={self.config.voice_name}, language={self.config.language}, break_duration={self.config.break_duration}, output_format={self.config.output_format}"
        )

    def is_access_token_expired(self) -> bool:
        return self.access_token is None or datetime.utcnow() >= self.token_expiry_time

    def auto_renew_access_token(self) -> str:
        if self.access_token is None or self.is_access_token_expired():
            logger.info(
                f"azure tts access_token doesn't exist or is expired, getting new one"
            )
            self.access_token = self.get_access_token()
            self.token_expiry_time = datetime.utcnow() + timedelta(minutes=9, seconds=1)
        return self.access_token

    def get_access_token(self) -> str:
        for retry in range(MAX_RETRIES):
            try:
                logger.info("Getting new access token")
                response = requests.post(self.TOKEN_URL, headers=self.TOKEN_HEADERS)
                response.raise_for_status()  # Will raise HTTPError for 4XX or 5XX status
                access_token = str(response.text)
                logger.info("Got new access token")
                return access_token
            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Network error while getting access token (attempt {retry + 1}/{MAX_RETRIES}): {e}"
                )
                if retry < MAX_RETRIES - 1:
                    sleep(2 ** retry)
                else:
                    raise e
        raise Exception("Failed to get access token")

    async def async_get_access_token(self, session) -> str:
        for retry in range(MAX_RETRIES):
            try:
                logger.info("Getting new access token")
                async with session.post(self.TOKEN_URL, headers=self.TOKEN_HEADERS) as response:
                    response.raise_for_status()
                    access_token = await response.text()
                    logger.info("Got new access token")
                    return access_token
            except aiohttp.ClientError as e:
                logger.warning(
                    f"Network error while getting access token (attempt {retry + 1}/{MAX_RETRIES}): {e}"
                )
                if retry < MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** retry)
                else:
                    raise e
        raise Exception("Failed to get access token")

    async def async_auto_renew_access_token(self, session) -> str:
        if self.access_token is None or self.is_access_token_expired():
            logger.info(
                f"azure tts access_token doesn't exist or is expired, getting new one"
            )
            self.access_token = await self.async_get_access_token(session)
            self.token_expiry_time = datetime.utcnow() + timedelta(minutes=9, seconds=1)
        return self.access_token

    async def async_text_to_speech(
            self,
            text: str,
            output_file: str,
            audio_tags: AudioTags,
    ):
        max_chars = 1800 if self.config.language.startswith("zh") else 3000
        text_chunks = split_text(text, max_chars, self.config.language)

        async with aiohttp.ClientSession() as session:
            audio_segments = await self.process_chunks(session, text_chunks, audio_tags)

            async with aiofiles.open(output_file, "wb") as outfile:
                for segment in audio_segments:
                    await outfile.write(segment)

        set_audio_tags(output_file, audio_tags)

    async def process_chunks(self, session, text_chunks, audio_tags):
        tasks = []
        for i, chunk in enumerate(text_chunks, 1):
            tasks.append(self.process_chunk(session, chunk, i, len(text_chunks), audio_tags))

        audio_segments = await asyncio.gather(*tasks)
        return audio_segments

    async def process_chunk(self, session, chunk, i, total_chunks, audio_tags):
        escaped_text = html.escape(chunk)
        escaped_text = escaped_text.replace(
            self.get_break_string().strip(),
            f" <break time='{self.config.break_duration}ms' /> ",
        )
        ssml = f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{self.config.language}'><voice name='{self.config.voice_name}'>{escaped_text}</voice></speak>"

        for retry in range(MAX_RETRIES):
            await self.async_auto_renew_access_token(session)
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": self.config.output_format,
                "User-Agent": "Python",
            }
            try:
                logger.info(
                    f"Processing chapter-{audio_tags.idx} <{audio_tags.title}>, chunk {i} of {total_chunks}, data length: {len(ssml)}"
                )
                async with session.post(self.TTS_URL, headers=headers, data=ssml.encode("utf-8")) as response:
                    response.raise_for_status()
                    content = await response.read()
                    logger.info(
                        f"Got response from Azure TTS for chapter-{audio_tags.idx}, response length: {len(content)}"
                    )
                    return content
            except aiohttp.ClientError as e:
                logger.warning(
                    f"Error while converting text to speech (attempt {retry + 1}): {e}"
                )
                if retry < MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** retry)
                else:
                    raise e
        return b''


    def get_break_string(self):
        return " @BRK#"

    def get_output_file_extension(self):
        if self.config.output_format.startswith("amr"):
            return "amr"
        elif self.config.output_format.startswith("ogg"):
            return "ogg"
        elif self.config.output_format.endswith("truesilk"):
            return "silk"
        elif self.config.output_format.endswith("pcm"):
            return "pcm"
        elif self.config.output_format.startswith("raw"):
            return "wav"
        elif self.config.output_format.startswith("webm"):
            return "webm"
        elif self.config.output_format.endswith("opus"):
            return "opus"
        elif self.config.output_format.endswith("mp3"):
            return "mp3"
        else:
            raise NotImplementedError(f"Unknown file extension for output format: {self.config.output_format}")

    def validate_config(self):
        # TODO: Need to dig into Azure properties, im not familiar with them, but look at OpenAI as ref example
        pass

    def estimate_cost(self, total_chars):
        return math.ceil(total_chars / 1000) * self.price

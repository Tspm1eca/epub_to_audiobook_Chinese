import logging
import os
import asyncio

from audiobook_generator.book_parsers.base_book_parser import get_book_parser
from audiobook_generator.config.general_config import GeneralConfig
from audiobook_generator.core.audio_tags import AudioTags
from audiobook_generator.tts_providers.base_tts_provider import get_async_tts_provider

logger = logging.getLogger(__name__)


def confirm_conversion():
    print("Do you want to continue? (y/n)")
    answer = input()
    if answer.lower() != "y":
        print("Aborted.")
        exit(0)


def get_total_chars(chapters):
    total_characters = 0
    for title, text in chapters:
        total_characters += len(text)
    return total_characters


class AudiobookGenerator:
    def __init__(self, config: GeneralConfig):
        self.config = config
        logger.setLevel(config.log)

    def __str__(self) -> str:
        return f"{self.config}"

    async def run(self):
        logger.info(f"🟢 Start - {os.path.basename(self.config.input_file)}")
        try:
            book_parser = get_book_parser(self.config)
            tts_provider = await get_async_tts_provider(self.config)

            os.makedirs(self.config.output_folder, exist_ok=True)
            chapters = book_parser.get_chapters(tts_provider.get_break_string())
            chapters = [(title, text) for title, text in chapters if text.strip()]
            logger.info(f"Chapters count: {len(chapters)}.")

            self.validate_chapters(len(chapters))

            logger.info(f"Converting chapters from {self.config.chapter_start} to {self.config.chapter_end}.")

            total_characters = get_total_chars(chapters[self.config.chapter_start - 1:self.config.chapter_end])
            logger.info(f"✨ Total characters in selected book chapters: {total_characters} ✨")
            rough_price = tts_provider.estimate_cost(total_characters)

            if not self.config.no_prompt and not self.config.preview and self.config.tts != 'edge':
                print(f"Estimate book voiceover would cost you roughly: ${rough_price:.2f}\n")
                confirm_conversion()

            semaphore = asyncio.Semaphore(5)  # Limit concurrent tasks
            tasks = []
            for idx, (title, text) in enumerate(chapters, start=1):
                if not (self.config.chapter_start <= idx <= self.config.chapter_end):
                    continue

                task = self.process_chapter(semaphore, idx, title, text, book_parser, tts_provider, len(chapters))
                tasks.append(task)

            await asyncio.gather(*tasks)

            logger.info(f"Audio Book finished - {os.path.basename(self.config.input_file)}🎉🎉🎉")

        except KeyboardInterrupt:
            logger.info("Job stopped by user.")
            exit()

    async def process_chapter(self, semaphore, idx, title, text, book_parser, tts_provider, total_chapters):
        async with semaphore:
            logger.info(f"Converting chapter {idx}/{total_chapters}: {title}, characters: {len(text)}")

            if self.config.output_text:
                text_file = os.path.join(self.config.output_folder, f"{idx:04d}_{title}.txt")
                with open(text_file, "w", encoding='utf-8') as file:
                    file.write(text)

            if self.config.preview:
                return

            output_file = os.path.join(self.config.output_folder, f"{idx:04d}_{title}.{tts_provider.get_output_file_extension()}")
            audio_tags = AudioTags(title, book_parser.get_book_author(), book_parser.get_book_title(), idx)

            await tts_provider.async_text_to_speech(text, output_file, audio_tags)

    def validate_chapters(self, num_chapters):
        if self.config.chapter_start < 1 or self.config.chapter_start > num_chapters:
            raise ValueError(f"Chapter start index {self.config.chapter_start} is out of range.")
        if self.config.chapter_end == -1:
            self.config.chapter_end = num_chapters
        if self.config.chapter_end > num_chapters:
            raise ValueError(f"Chapter end index {self.config.chapter_end} is out of range.")
        if self.config.chapter_start > self.config.chapter_end:
            raise ValueError("Chapter start index cannot be larger than chapter end index.")


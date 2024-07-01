from cgitb import text
import logging
import re
from typing import List, Tuple
import opencc

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from audiobook_generator.book_parsers.base_book_parser import BaseBookParser
from audiobook_generator.config.general_config import GeneralConfig

logger = logging.getLogger(__name__)
converter = opencc.OpenCC('t2s')
# URL 的正则表达式
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")
# 使用正则表达式匹配 [数字] 或 数字
NODE_PATTERN = re.compile(r'(href=.*?>)註?\[?\d+\]?(<)')


class EpubBookParser(BaseBookParser):
    def __init__(self, config: GeneralConfig):
        super().__init__(config)
        logger.setLevel(config.log)
        self.book = epub.read_epub(
            self.config.input_file, {"ignore_ncx": True})

    def __str__(self) -> str:
        return super().__str__()

    def footnote_repalcer(self, match):
        # 去除註腳
        return f'{match.group(1)}{match.group(2)}'

    def validate_config(self):
        if self.config.input_file is None:
            raise ValueError("Epub Parser: Input file cannot be empty")
        if not self.config.input_file.endswith(".epub"):
            raise ValueError(
                f"Epub Parser: Unsupported file format: {self.config.input_file}")

    def get_book(self):
        return self.book

    def get_book_title(self) -> str:
        if self.book.get_metadata('DC', 'title'):
            return self.book.get_metadata("DC", "title")[0][0]
        return "Untitled"

    def get_book_author(self) -> str:
        if self.book.get_metadata('DC', 'creator'):
            return self.book.get_metadata("DC", "creator")[0][0]
        return "Unknown"

    def get_chapters(self, break_string) -> List[Tuple[str, str]]:
        chapters = []
        t2s = False
        for doc_id in self.book.spine:
            title = ""
            item = self.book.get_item_with_id(doc_id[0])
            soup = BeautifulSoup(item.content, "lxml-xml")

            # 使用'h1','h2'...標籤找標題
            for tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                if tag := soup.find(tag_name):
                    title = tag.text.strip()
                    break

            if not title:
                # 如果沒有找到標題，使用<p>標籤找標題
                paragraphs = [p.get_text().strip()
                              for p in soup.find_all('p') if p.get_text()]
                if paragraphs:
                    # 用前兩段有文字的<p>作為標題，限20字符
                    title = '_'.join(paragraphs[:2])[:20]
                else:
                    continue

            logger.debug(f"title: <{title}>")
            title = self._sanitize_title(title, break_string)
            logger.debug(f"Sanitized title: <{title}>")

            body_content = soup.find('body')    # 提取文章主體

            # 去除註腳數字[1] / 1
            if self.config.remove_endnotes:
                text_soup = str(body_content)
                # 使用正则表达式匹配 [数字] 或 数字
                text_soup = re.sub(
                    NODE_PATTERN, self.footnote_repalcer, text_soup)
                # # 使用正则表达式匹配 URL
                text_soup = re.sub(URL_PATTERN, "", text_soup)

                body_content = BeautifulSoup(text_soup, "lxml-xml")

            raw = body_content.get_text(strip=False)
            logger.debug(f"Raw text: <{raw[:]}>")

            # Replace excessive whitespaces and newline characters based on the mode
            if self.config.newline_mode == "single":
                cleaned_text = re.sub(r"[\n]+", break_string, raw.strip())
            elif self.config.newline_mode == "double":
                cleaned_text = re.sub(r"[\n]{2,}", break_string, raw.strip())
            elif self.config.newline_mode == "none":
                cleaned_text = re.sub(r"[\n]+", " ", raw.strip())
            else:
                raise ValueError(
                    f"Invalid newline mode: {self.config.newline_mode}")

            logger.debug(f"Cleaned text step 1: <{cleaned_text[:]}>")
            cleaned_text = re.sub(r"\s+", " ", cleaned_text)
            logger.debug(f"Cleaned text step 2: <{cleaned_text[:100]}>")

            # 如果文本是繁體中文，但輸出語音為簡體中文，則把文本轉換為簡體中文
            if any(td in self.config.language for td in ["zh-TW", "zh-HK"]) and self.config.voice_name.startswith("zh-CN"):
                if not t2s:
                    logger.info("繁 -> 簡")
                # 转换为简体中文，防止語音出現問題，例如：為什麼，金額...
                cleaned_text = converter.convert(cleaned_text)
                t2s = True  # 繁 -> 简 標是

            chapters.append((title, cleaned_text))
            soup.decompose()

        return chapters

    @staticmethod
    def _sanitize_title(title, break_string) -> str:
        # replace MAGIC_BREAK_STRING with a blank space
        # strip incase leading bank is missing
        title = title.replace(break_string, " ")
        sanitized_title = re.sub(r"[^\w\s]", "", title, flags=re.UNICODE)
        sanitized_title = re.sub(r"\s+", "_", sanitized_title.strip())
        return sanitized_title

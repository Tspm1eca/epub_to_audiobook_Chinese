import logging
import regex as re
import opencc
# import concurrent.futures
import os
import warnings

from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub

from audiobook_generator.book_parsers.base_book_parser import BaseBookParser
from audiobook_generator.config.general_config import GeneralConfig

logger = logging.getLogger(__name__)
converter = opencc.OpenCC('t2s')
warnings.filterwarnings("ignore", category=FutureWarning)


class EpubBookParser(BaseBookParser):
    # URL 的正则表达式
    # URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")
    URL_PATTERN = re.compile(
        r"((?:https?|ftps?|gopher|telnet|nntp)://[-%()_.!~*';/?:@&=+$,A-Za-z0-9]+|mailto:[-%()_.!~*';/?:@&=+$,A-Za-z0-9]+|news:[-%()_.!~*';/?:@&=+$,A-Za-z0-9]+)")
    FN_NOTE_PATTERN = re.compile(r'#')
    CHINESE_CHAR_PATTERN = re.compile(r'[\u4e00-\u9fff]')
    # >= 2個任何文字，用於「註1」情況
    TEXT_PATTERN = re.compile(r'\p{L}{2,}', re.UNICODE)
    SYMBOL_PATTERN = r"⤴↑↺"

    def __init__(self, config: GeneralConfig):
        super().__init__(config)

        logger.setLevel(config.log)

        self.book = epub.read_epub(
            self.config.input_file, {"ignore_ncx": True})

        self.files = {}
        self.t2sed = False

        if self.config.language == "zh-CN":
            self.fnote_prefix = " （注解："
            self.fnote_suffix = " 回到正文） "
        elif self.config.language in ["zh-TW", "zh-HK"]:
            self.fnote_prefix = " （註解："
            self.fnote_suffix = " 回到正文） "
        else:
            self.fnote_prefix = " (Note: "
            self.fnote_suffix = " Note End.) "

        self._load_files()

    def __str__(self) -> str:
        return super().__str__()

    def validate_config(self):
        if self.config.input_file is None:
            raise ValueError("Epub Parser: Input file cannot be empty")
        if not self.config.input_file.endswith(".epub"):
            raise ValueError(
                f"Epub Parser: Unsupported file format: {self.config.input_file}")

    def count_chinese_and_english_words(s):
        # 中文字符計數
        chinese_count = sum(1 for c in s if '\u4e00' <= c <= '\u9fff')

        # 英文單詞計數，使用正則表達式匹配單詞
        english_words = re.findall(r'\b[a-zA-Z]+\b', s)
        english_word_count = len(english_words)

        return chinese_count, english_word_count

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

    def get_chapters(self, break_string):
        self.break_string = break_string

        # with concurrent.futures.ThreadPoolExecutor() as executor:
        #     chapters = list(executor.map(
        #         self._chapter_process, self.files.items()))

        chapters = [self._chapter_process(item)
                    for item in self.files.items()]

        chapters = [chapter for chapter in chapters if all(chapter)]

        return chapters

    def _load_files(self):
        """ 載入所有Epub的內容 """
        # 获取所有html類文件，結果為字典：part0052.html:<EpubHtml:id586:text/part0052.html>
        for doc_id in self.book.spine:
            item = self.book.get_item_with_id(doc_id[0])
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                file_name = os.path.basename(item.get_name())
                content = item.get_body_content()
                soup = BeautifulSoup(content, 'lxml')
                # 清理id
                self._clear_id(soup)

                self.files[file_name] = soup

    def _clear_id(self, soup):
        # 去除title 跳轉, 防止目錄跳轉被誤當標籤
        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            tag.attrs.pop('id', None)

        # 去除 body 的 id，防止被誤當標籤
        soup.find('body').attrs.pop('id', None)

    def _chapter_process(self, file_item):
        file_name, soup = file_item

        # 文章標題
        title = self._title_find(file_name, soup)
        if not title:
            return (None, None)

        text_soup = soup.get_text() if not (
            self.config.remove_endnotes or self.config.fnote_transplant) else self._fnote_process(file_name, soup)

        if not self.config.test_mode:
            # Replace excessive whitespaces and newline characters based on the mode
            cleaned_text = self._text_cleanup(text_soup.strip())

            # 如果文本是繁體中文，但輸出語音為簡體中文，則把文本轉換為簡體中文
            if self.config.language in ["zh-TW", "zh-HK"] and self.config.voice_name.startswith("zh-CN"):
                # 繁轉簡
                cleaned_text = self._t2s(cleaned_text)
        else:
            cleaned_text = text_soup.strip()

        self.files[file_name] = None
        soup.decompose()

        return (title, cleaned_text)

    def _title_find(self, file_name, soup):
        """ 找標題 """
        title = ""

        # 使用'h1','h2'...標籤找標題
        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
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
                return None

        logger.debug(f"title: <{title}>")
        title = self._sanitize_title(title, self.break_string)
        logger.debug(f"Sanitized title: <{title}>")

        return title

    @staticmethod
    def _sanitize_title(title, break_string) -> str:
        # replace MAGIC_BREAK_STRING with a blank space
        # strip incase leading bank is missing
        title = title.replace(break_string, " ")
        sanitized_title = re.sub(r"[^\w\s]", "", title, flags=re.UNICODE)
        sanitized_title = re.sub(r"\s+", "_", sanitized_title.strip())

        return sanitized_title

    def _text_cleanup(self, text):
        """ Replace excessive whitespaces and newline characters based on the mode """
        if self.config.newline_mode == "single":
            cleaned_text = re.sub(
                r"[\n]+", self.break_string, text.strip())
        elif self.config.newline_mode == "double":
            cleaned_text = re.sub(
                r"[\n]{2,}", self.break_string, text.strip())
        elif self.config.newline_mode == "none":
            cleaned_text = re.sub(r"[\n]+", " ", text.strip())
        else:
            raise ValueError(
                f"Invalid newline mode: {self.config.newline_mode}")

        logger.debug(f"Cleaned text step 1: <{cleaned_text[:]}>")
        cleaned_text = re.sub(r"\s+", " ", cleaned_text)
        logger.debug(f"Cleaned text step 2: <{cleaned_text[:100]}>")

        return cleaned_text

    def _t2s(self, text):
        """ 繁轉簡 """

        if not self.t2sed:
            logger.info("繁 -> 簡")
            self.t2sed = True  # 繁 -> 简 標是

        # 转换为简体中文，防止語音出現問題，例如：為什麼，金額...
        return converter.convert(text)

    def _fnote_process(self, file_name, soup):
        """ 移植註腳 / 移除註腳 + 清空註腳內容 """
        # 查找所有註腳和連結
        for fnote in soup.find_all('a', href=self.FN_NOTE_PATTERN):
            all_text = ''.join(fnote.stripped_strings)  # 递歸找出 a tag 中的所有文字
            # 被處理後的註腳內容href中沒有# | 處理「註1」情況 | 處理只有圖片的註腳
            if "#" not in fnote['href'] or self.TEXT_PATTERN.search(all_text) or (not all_text and not fnote.find('img')):
                continue

            # 提取href中的文件名和ID
            href_file, href_id = fnote['href'].split('#')
            # 尋找目標文件和ID
            # (因為有機會註腳內容不在同一個文件中)
            target_soup = self.files.get(href_file, soup)
            fnote_element = target_soup.find(
                id=href_id) if target_soup else None

            if not fnote_element:
                continue

            # 移除註腳內容中的連結，防止註腳內容被當作標籤處理
            for tag_a in ([fnote_element] if fnote_element.name == 'a' else fnote_element.find_all('a')):
                tag_a['href'] = ''

            # 如果找不到註腳內容
            # 循環向上搜尋父元素，直到找到任何文字，確保註腳內容完整
            while (fnote_content := fnote_element.get_text()) == fnote.string:
                fnote_element = fnote_element.find_parent()

            new_fnote_content = ""
            fnote.string = fnote.string or ""

            if self.config.fnote_transplant:
                # 找出註腳內容 + 移除註腳標籤和符號表內的符號
                cleaned_fnote_content = re.sub(
                    fr"[{re.escape(fnote.string)}{self.SYMBOL_PATTERN}]", '', fnote_content)
                # 移植註腳內容到註腳標籤
                if self.CHINESE_CHAR_PATTERN.search(cleaned_fnote_content):
                    # "註解： 註解內容 註解完畢。"
                    new_fnote_content = f"{self.fnote_prefix}{cleaned_fnote_content.strip()}{self.fnote_suffix}"

            fnote.string.replace_with(new_fnote_content)
            # 移除註腳內容
            fnote_element.clear()

        # 去除Url
        cleaned_text = re.sub(self.URL_PATTERN, "", soup.get_text())
        return cleaned_text

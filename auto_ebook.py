import os
import shutil
import subprocess
import platform
from pathlib import Path
import logging
import sys
import re
import time

# --- 配置 ---
class Config:
    """集中管理所有配置"""
    def __init__(self):
        self.platform = platform.system()
        self.base_path = self._get_base_path()
        script_dir = Path(__file__).parent.resolve()
        self.e2ab_script_path = script_dir / 'main.py'

        # 從環境變量讀取 API 金鑰，如果不存在則為 None
        self.api_key = os.environ.get("API_KEY", "sk-000")
        self.base_url = "api.openai.com"
        self.llm_model = "gemini-2.5-pro"

        self.subprocess_log_file = self.base_path / 'output.log'
        self.script_log_file = script_dir / 'auto_ebook.log'
        self.log_size_limit = 100 * 1024 * 1024  # 100MB

    def _get_base_path(self):
        if self.platform == 'Windows':
            return Path(r'D:\Downloads\XXX')
        elif self.platform == 'Darwin':
            return Path(r'/Users/user/Downloads/XXX')
        elif self.platform == 'Linux':
            return Path(r'/home/user/Downloads/XXX')
        else:
            raise NotImplementedError(f"不支持的操作系统: {self.platform}")

def count_chinese_chars(text):
    """Counts the number of Chinese characters in a string."""
    # This regex matches CJK Unified Ideographs, covering both simplified and traditional.
    return len(re.findall(r'[\u4e00-\u9fff]', text))

# --- 日誌 ---
def check_and_clear_log_file(log_file, size_limit):
    """檢查日誌文件大小，如果超過限制則清空"""
    if log_file.exists() and log_file.stat().st_size > size_limit:
        try:
            log_file.unlink()
            print(f"日誌文件 {log_file} 已超過 {size_limit // 1024 // 1024}MB，已清空。")
        except OSError as e:
            print(f"清空日誌文件 {log_file} 失敗: {e}")

def setup_logging(log_file):
    """設置日誌記錄器"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)           #NOTE REMOVE ME in Linux
        ]
    )

# --- 核心功能 ---
def run_conversion(config, epub_path, output_dir, **kwargs):
    """
    統一的轉換命令執行函數
    :param config: Config 對象
    :param epub_path: EPUB 文件路徑
    :param output_dir: 輸出目錄
    :param kwargs: 其他傳遞給 main.py 的參數
    """
    base_cmd = [
        'python3', str(config.e2ab_script_path),
        '--tts', 'edge',
        '--voice_name', 'zh-CN-YunxiNeural',
        '--language', 'zh-TW',
        '--break_duration', '500',
        '--voice_volume', '100',
        '--output_text',
        str(epub_path),
        str(output_dir)
    ]

    # 根據 kwargs 動態添加參數
    if kwargs.get('preview'):
        base_cmd.insert(6, '--preview')
    if kwargs.get('fnote_transplant'):
        base_cmd.insert(6, '--fnote_transplant')
    if chapter_start := kwargs.get('chapter_start'):
        base_cmd.extend(['--chapter_start', str(chapter_start)])
    if kwargs.get('sum_only'):
        base_cmd.append('--sum_only')

    # 如果 API 金鑰存在，並且不是預覽模式，則添加摘要相關參數
    if config.api_key and not kwargs.get('preview'):
        base_cmd.extend([
            '--sum_model', config.llm_model,
            '--sum_api', config.api_key,
            '--sum_url', config.base_url
        ])

    logging.info(f"執行命令: {' '.join(base_cmd)}")

    try:
        # 使用 with open 來確保文件句柄被正確關閉
        with open(config.subprocess_log_file, 'a', encoding='utf-8') as log_f:
            subprocess.run(
                base_cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                check=True  # 如果命令返回非零退出碼，則拋出異常
            )
        logging.info(f"成功處理: {epub_path.name}")
    except subprocess.CalledProcessError as e:
        logging.error(f"處理失敗: {epub_path.name}\n錯誤: {e}")
    except Exception as e:
        logging.error(f"發生未知錯誤: {epub_path.name}\n錯誤: {e}")


def check_incomplete_book(book_dir):
    """檢查書籍文件夾，確定是否需要從特定章節繼續"""
    txt_files = list(book_dir.glob('*.txt'))
    mp3_files = list(book_dir.glob('*.mp3'))

    if not txt_files and not mp3_files:
        # 完全沒有處理過
        return 1

    existing_mp3_stems = {f.stem for f in mp3_files}
    missing_chapters = []

    for txt_file in txt_files:
        # 如果 MP3 已存在，則跳過
        if txt_file.stem in existing_mp3_stems:
            continue

        # 拆分檔名以獲取章節部分，例如 '001_...'
        parts = txt_file.stem.split('_', 1)
        if len(parts) < 2:
            continue  # 檔名格式不符（沒有 '_'），跳過

        chapter_part = parts[0]

        # 檢查章節部分是否為純數字。如果包含 'S' 或其他非數字字符，則跳過。
        if not chapter_part.isdigit():
            continue

        # 如果是常規章節，則提取序列號並添加到缺失列表中
        missing_chapters.append(int(chapter_part))

    if not missing_chapters:
        return None # 所有章節都已完成

    # 從缺失的最小章節的前一章開始，以確保連貫性
    start_chapter = min(missing_chapters)
    return max(1, start_chapter -1)


def process_book_directory(book_dir, config):
    """處理單個書籍文件夾（檢查完整性、摘要等）"""
    logging.info(f"檢查文件夾: {book_dir.name}")
    epub_files = list(book_dir.glob('*.epub'))
    if not epub_files:
        logging.warning(f"文件夾 {book_dir.name} 中沒有找到 .epub 文件，跳過。")
        return

    epub_path = epub_files[0]

    # 1. 檢查是否需要繼續轉換
    start_from = check_incomplete_book(book_dir)
    if start_from:
        logging.info(f"檢測到《{epub_path.stem}》未完成，將從第 {start_from} 章開始。")
        run_conversion(config, epub_path, book_dir, chapter_start=start_from, fnote_transplant=True)
        return # 完成後退出，避免重複檢查摘要

    # 2. 檢查並生成章節摘要及對應 MP3
    if not start_from and config.api_key:
        needs_sum_only_run = False
        all_txt_files = sorted(book_dir.glob('*.txt'))
        existing_mp3_stems = {f.stem for f in book_dir.glob('*.mp3')}

        # 過濾出常規章節文件
        chapter_files = [
            f for f in all_txt_files
            if '_' in f.stem and not f.stem.split('_', 1)[0].endswith('S')
        ]

        for txt_file in chapter_files:
            name_parts = txt_file.stem.split('_', 1)
            if len(name_parts) < 2:
                continue

            summary_stem = f"{name_parts[0]}S_{name_parts[1]}"
            summary_file = txt_file.with_name(f"{summary_stem}.txt")

            # 情況一：摘要 .txt 存在，但 .mp3 缺失
            if summary_file.exists() and summary_stem not in existing_mp3_stems:
                logging.info(f"檢測到摘要 '{summary_file.name}' 缺少對應的 MP3 文件。")
                needs_sum_only_run = True
                break

            # 情況二：摘要 .txt 不存在，且原文夠長，需要生成
            if not summary_file.exists():
                try:
                    content = txt_file.read_text(encoding='utf-8')
                    char_count = count_chinese_chars(content)
                    if char_count > 2000:
                        logging.info(f"檢測到章節 '{txt_file.name}' 需要生成摘要 (長度: {char_count} > 2000)。")
                        needs_sum_only_run = True
                        break
                except Exception as e:
                    logging.error(f"讀取文件 '{txt_file.name}' 失敗: {e}")

        if needs_sum_only_run:
            # logging.info(f"為《{epub_path.stem}》運行 --sum_only 模式來生成或補全摘要及音頻。")
            run_conversion(config, epub_path, book_dir, sum_only=True)


def main():
    """主執行函數"""
    start_time = time.time()
    config = Config()

    # 檢查並清理兩個日誌文件
    check_and_clear_log_file(config.subprocess_log_file, config.log_size_limit)
    check_and_clear_log_file(config.script_log_file, config.log_size_limit)

    # 設置腳本自身日誌
    setup_logging(config.script_log_file)

    if not config.e2ab_script_path.exists():
        logging.error(f"核心腳本 'main.py' 未在預期路徑找到: {config.e2ab_script_path}")
        return

    base_path = config.base_path
    logging.info(f"--- 開始掃描工作目錄: {base_path} ---")

    # 處理根目錄下的新 EPUB 文件
    for item in base_path.glob('*.epub'):
        logging.info(f"發現新的 EPUB 文件: {item.name}")
        book_dir = base_path / item.stem
        book_dir.mkdir(exist_ok=True)

        destination = book_dir / item.name
        shutil.move(str(item), str(destination))
        logging.info(f"已將 {item.name} 移動到 {destination} 及生成所有章節文本")

        # 預覽和完整轉換
        run_conversion(config, destination, book_dir, preview=True, fnote_transplant=True)
        run_conversion(config, destination, book_dir, fnote_transplant=True)

    # 檢查並處理所有子文件夾
    for item in base_path.iterdir():
        if item.is_dir() and not item.name.startswith(('.', '@')):
            process_book_directory(item, config)

    end_time = time.time()
    elapsed_time = end_time - start_time
    minutes, seconds = divmod(elapsed_time, 60)
    logging.info(f"--- 所有任務處理完畢 ({int(minutes)}:{seconds:.2f}min) ---")


if __name__ == '__main__':
    main()
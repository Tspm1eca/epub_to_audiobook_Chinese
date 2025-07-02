import os
import re
import asyncio
import aiohttp
import logging
from audiobook_generator.config.general_config import GeneralConfig
from audiobook_generator.core.audio_tags import AudioTags
from audiobook_generator.tts_providers.base_tts_provider import get_async_tts_provider

# Setup logging
logger = logging.getLogger(__name__)
# Prompt as requested
SUMMARY_PROMPT = """
# 角色
你是一位专业的文章阅读助手和摘要专家。

# 任务
为接下来的文章生成一份专业的摘要。

# 工作流程
你必须严格按照以下两步工作流来完成任务：

## 步骤一：分析文章（内心思考，无需输出此部分）
1.  **识别中心议题**：用一句话概括文章最核心的主张或议题。
2.  **提取关键信息**：全面梳理并列出本章所有的关键信息。
3.  **洞察独特之处**：找出文章提出的最独特或最具启发性的观点、区别性概念或反直觉的结论。
4.  **处理不确定性**：如果原文中的某个论点含糊不清或存在矛盾，请在摘要中客观地反映这一点。

## 步骤二：生成摘要
根据你在【步骤一】的分析，综合所有识别出的要点，撰写一份摘要。

# 约束条件
-   **内容要求**：摘要必须整合【步骤一】中分析出的所有核心内容，逻辑清晰，忠于原文。
-   **格式要求**：
    -   语言：简体中文。
    -   格式：纯文本，严禁使用任何Markdown标记。
    -   换行：不需要换行，直接连续输出。
    -   字数：严格控制在最少500字，最多800字以内。
    -   內容：只需要返回摘要内容，不需要任何多余的内容

请开始分析下面的文章：
"""

class AudioSummaryGenerator:
    def __init__(self, config: GeneralConfig):
        self.config = config
        logger.setLevel(config.log)

    def _count_chinese_chars(self, text: str) -> int:
        """Counts the number of Chinese characters in a string."""
        # This regex matches CJK Unified Ideographs, covering both simplified and traditional.
        return len(re.findall(r'[\u4e00-\u9fff]', text))

    def _summary_format(self, text: str) -> str:
        format_text = f"(本章总结){text}(总结结束)"
        return format_text

    def _llm_url_format(self, base_url: str) -> str:
        """ BASE_URL 格式化 """
        # Remove leading/trailing whitespace
        base_url = base_url.strip()

        # Add https:// if not present
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url

        # Remove trailing slash if present
        base_url = base_url.rstrip('/')

        # Add /v1/chat/completions if not present
        if not base_url.endswith('/v1/chat/completions'):
            # If /v1 is present but not followed by /chat/completions, truncate to /v1
            if base_url.endswith('/v1'):
                base_url += '/chat/completions'
            elif '/v1' not in base_url:
                base_url += '/v1/chat/completions'

        return base_url


    async def _get_summary_from_llm_async(self, session: aiohttp.ClientSession, text: str, filename: str) -> str:
        """Sends text to LLM and gets a summary asynchronously."""
        headers = {
            "Authorization": f"Bearer {self.config.sum_api}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.config.sum_model,
            "messages": [
                {"role": "system", "content": SUMMARY_PROMPT.strip()},
                {"role": "user", "content": text}
            ],
            "temperature": 0.7,
            "stream": False
        }

        base_url = self._llm_url_format(self.config.sum_url)
        max_retries = 4
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Requesting LLM for {filename} (Attempt {attempt + 1}/{max_retries + 1})")
                async with session.post(base_url, headers=headers, json=data, timeout=300) as response:
                    response.raise_for_status()
                    result = await response.json()
                    summary = result['choices'][0]['message']['content'].strip()
                    return self._summary_format(summary)
            except aiohttp.ClientError as e:
                logger.warning(f"API request for {filename} failed: {e}")
                if attempt >= max_retries:
                    logger.error(f"API request for {filename} failed after {max_retries + 1} attempts.")
                    return ""
            except (KeyError, IndexError) as e:
                logger.warning(f"Failed to parse LLM response for {filename}: {e}")
                if attempt >= max_retries:
                    # The response object might not be available here if the error is ClientError
                    # but we try to log it if possible.
                    try:
                        response_text = await response.text()
                        logger.error(f"Failed to parse LLM response for {filename} after {max_retries + 1} attempts.\nResponse: {response_text}")
                    except NameError:
                        logger.error(f"Failed to parse LLM response for {filename} after {max_retries + 1} attempts.")
                    return ""

            if attempt < max_retries:
                logger.info(f"Retrying for {filename} in 5s...")
                await asyncio.sleep(5)
        return ""

    async def _process_llm_task(self, semaphore: asyncio.Semaphore, session: aiohttp.ClientSession, task: dict):
        """Wrapper to process a single LLM task with semaphore."""
        async with semaphore:
            logger.info(f"Generating: {task['filename']}")
            summary_content = await self._get_summary_from_llm_async(session, task['content'], task['filename'])
            if summary_content:
                try:
                    with open(task['summary_txt_path'], 'w', encoding='utf-8') as f:
                        f.write(summary_content)
                    logger.info(f"Successfully generated: {os.path.basename(task['summary_txt_path'])}")
                except Exception as e:
                    logger.error(f"Could not write summary file {task['summary_txt_path']}: {e}")
            else:
                logger.warning(f"Failed to generate summary for {task['filename']}.")

    async def _run_llm_tasks(self, tasks_for_llm: list):
        """Runs all LLM summary tasks asynchronously with a concurrency limit."""
        semaphore = asyncio.Semaphore(5)
        async with aiohttp.ClientSession() as session:
            async_tasks = [self._process_llm_task(semaphore, session, task) for task in tasks_for_llm]
            await asyncio.gather(*async_tasks)

    async def run(self):
        output_folder = os.path.dirname(self.config.input_file)
        logger.info(f"Starting summary generation: {os.path.basename(self.config.input_file)}")

        if not os.path.isdir(output_folder):
            logger.error(f"Output folder not found: {output_folder}")
            return

        file_pattern = re.compile(r'^\d{4}_.*\.txt$')
        files_to_process = sorted([f for f in os.listdir(output_folder) if file_pattern.match(f)])

        tasks_for_llm = self.collect_llm_tasks(files_to_process, output_folder)

        if tasks_for_llm:
            logger.info(f"Found {len(tasks_for_llm)} file(s) to summarize.")
            await self._run_llm_tasks(tasks_for_llm)
        else:
            logger.info("No new summaries needed.")

        await self._run_tts_tasks(files_to_process, output_folder)
        logger.info(f"Audio Summary finished - {os.path.basename(self.config.input_file)}🎈🎈🎈")

    def collect_llm_tasks(self, files_to_process, output_folder):
        tasks_for_llm = []
        for filename in files_to_process:
            summary_txt_filename = f"{filename[:4]}S{filename[4:]}"
            summary_txt_path = os.path.join(output_folder, summary_txt_filename)
            summary_mp3_path = os.path.join(output_folder, summary_txt_filename.replace('.txt', '.mp3'))

            if os.path.exists(summary_mp3_path) or os.path.exists(summary_txt_path):
                continue

            source_path = os.path.join(output_folder, filename)
            try:
                with open(source_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if self._count_chinese_chars(content) > 2000:
                    tasks_for_llm.append({
                        'filename': filename,
                        'content': content,
                        'summary_txt_path': summary_txt_path
                    })
                else:
                    logger.info(f"Skipped {filename} (less than 2000 characters).")
            except Exception as e:
                logger.error(f"Could not read source file {source_path}: {e}")
        return tasks_for_llm

    async def _run_tts_tasks(self, files_to_process, output_folder):
        logger.info("Starting TTS conversion for all available summaries.")
        tts_provider = await get_async_tts_provider(self.config)
        semaphore = asyncio.Semaphore(5)
        tasks = []

        for filename in files_to_process:
            summary_txt_filename = f"{filename[:4]}S{filename[4:]}"
            summary_txt_path = os.path.join(output_folder, summary_txt_filename)
            summary_mp3_path = os.path.join(output_folder, summary_txt_filename.replace('.txt', '.mp3'))

            if os.path.exists(summary_mp3_path) or not os.path.exists(summary_txt_path):
                continue

            tasks.append(self._process_tts_task(semaphore, summary_txt_path, summary_mp3_path, filename, tts_provider))

        if tasks:
            await asyncio.gather(*tasks)
        else:
            logger.info("No new summaries to convert to audio.")

    async def _process_tts_task(self, semaphore, summary_txt_path, summary_mp3_path, filename, tts_provider):
        async with semaphore:
            try:
                with open(summary_txt_path, 'r', encoding='utf-8') as f:
                    summary_content = f.read()
                if summary_content:
                    id_tag = filename[:4]
                    sum_count = self._count_chinese_chars(summary_content)
                    logger.info(f"Converting MP3 ({sum_count} words): {os.path.basename(summary_txt_path)}")
                    audio_tags = AudioTags("", "", "", id_tag)
                    await tts_provider.async_text_to_speech(summary_content, summary_mp3_path, audio_tags)
                else:
                    logger.warning(f"Summary file {summary_txt_path} is empty, skipping TTS.")
            except Exception as e:
                logger.error(f"Could not process summary file {summary_txt_path} for TTS: {e}")




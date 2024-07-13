# EPUB to Audiobook Converter [![Discord](https://img.shields.io/discord/1177631634724491385?label=Discord&logo=discord&logoColor=white)](https://discord.com/invite/pgp2G8zhS7)

*Join our [Discord](https://discord.com/invite/pgp2G8zhS7) server for any questions or discussions.*

This project provides a command-line tool to convert EPUB ebooks into audiobooks. It now supports both the [Microsoft Azure Text-to-Speech API](https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/rest-text-to-speech) (alternativly [EdgeTTS](https://github.com/rany2/edge-tts)) and the [OpenAI Text-to-Speech API](https://platform.openai.com/docs/guides/text-to-speech) to generate the audio for each chapter in the ebook. The output audio files are optimized for use with [Audiobookshelf](https://github.com/advplyr/audiobookshelf).

*This project is developed with the help of ChatGPT.*

## 魔改版本（對比原版）
### 以下只對edge-tts的修改
- 去除內文中的註腳標籤
- 去除內文中的URL
- 如果文本是繁體中文，但用戶選擇輸出的語音為簡體中文，則把文本轉換為簡體中文（方便使用zh-CN-YunxiNeural和其他zh-CN系列聲音）
- 優化edge-tts轉換（提升約1/3 ~ 1/2 速度）
- 修正音質問題
- 修正小數點後數字消失問題，例如：6.9公里 轉換後變成 6.公里
- 使用EPub的spine次序排列標題名，不會再有轉換後亂序的問題
- 取消在使用edge模式下，出現"Do you want to continue? (y/n)" 再次確定 （免費還要確定什麼？其他模式還是有的）
- 增加註腳移植功能（ --fnote_transplant ）:
  - 移植註腳內容到內文中（見下文）
  - 去除所有不包含任何中文字符的註腳內容
  - 注意： 如果同時使用 --fnote_transplant 和 --remove_endnotes，以--fnote_transplant 優先，自動無視--remove_endnotes

## 註腳移植

- 書本文章內容：
```
你好嗎？如果覺得閱讀很費眼晴[1]，不如試試聽書[2]。

[1] 這只是個人假設不是完全的事實。
[2] Hello World
```
- 使用註腳移植後：
  - [2]不包含任何中文字符，所以被去除
```
你好嗎？如果覺得閱讀很費眼晴（註解：這只是個人假設不是完全的事實。註解完畢。） ，不如試試聽書。
```

## Audio Sample

If you're interested in hearing a sample of the audiobook generated by this tool, check the links bellow. 

- [Azure TTS Sample](https://audio.com/paudi/audio/0008-chapter-vii-agricultural-experience)
- [OpenAI TTS Sample](https://audio.com/paudi/audio/openai-0008-chapter-vii-agricultural-experience-i-had-now-been-in)
- Edge TTS Sample: the voice is almost the same as Azure TTS

## Requirements

- Python 3.6+ Or ***Docker***
- For using *Azure TTS*, A Microsoft Azure account with access to the [Microsoft Cognitive Services Speech Services](https://portal.azure.com/#create/Microsoft.CognitiveServicesSpeechServices) is required.
- For using *OpenAI TTS*, OpenAI [API Key](https://platform.openai.com/api-keys) is required.
- For using *Edge TTS*, no API Key is required.

## Audiobookshelf Integration

The audiobooks generated by this project are optimized for use with [Audiobookshelf](https://github.com/advplyr/audiobookshelf). Each chapter in the EPUB file is converted into a separate MP3 file, with the chapter title extracted and included as metadata.

![demo](./examples/audiobookshelf.png)

### Chapter Titles

Parsing and extracting chapter titles from EPUB files can be challenging, as the format and structure may vary significantly between different ebooks. The script employs a simple but effective method for extracting chapter titles, which works for most EPUB files. The method involves parsing the EPUB file and looking for the `title` tag in the HTML content of each chapter. If the title tag is not present, a fallback title is generated using the first few words of the chapter text.

Please note that this approach may not work perfectly for all EPUB files, especially those with complex or unusual formatting. However, in most cases, it provides a reliable way to extract chapter titles for use in Audiobookshelf.

When you import the generated MP3 files into Audiobookshelf, the chapter titles will be displayed, making it easy to navigate between chapters and enhancing your listening experience.

## Installation

1. Clone this repository:

    ```bash
    git clone https://github.com/p0n1/epub_to_audiobook.git
    cd epub_to_audiobook
```

2. Create a virtual environment and activate it:

    ```bash
    python3 -m venv venv
    source venv/bin/activate
```

3. Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Set the following environment variables with your Azure Text-to-Speech API credentials, or your OpenAI API key if you're using OpenAI TTS:

    ```bash
    export MS_TTS_KEY=<your_subscription_key> # for Azure
    export MS_TTS_REGION=<your_region> # for Azure
    export OPENAI_API_KEY=<your_openai_api_key> # for OpenAI
    ```

## Usage

To convert an EPUB ebook to an audiobook, run the following command, specifying the TTS provider of your choice with the `--tts` option:

```bash
python3 main.py <input_file> <output_folder> [options]
```

To check the latest option descriptions for this script, you can run the following command in the terminal:

```bash
python3 main.py -h
```

```bash
usage: main.py [-h] [--tts {azure,openai,edge}]
               [--log {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [--preview]
               [--no_prompt] [--language LANGUAGE]
               [--newline_mode {single,double,none}]
               [--title_mode {auto,tag_text,first_few}]
               [--chapter_start CHAPTER_START] [--chapter_end CHAPTER_END]
               [--output_text] [--remove_endnotes] [--voice_name VOICE_NAME]
               [--output_format OUTPUT_FORMAT] [--model_name MODEL_NAME]
               [--voice_rate VOICE_RATE] [--voice_volume VOICE_VOLUME]
               [--voice_pitch VOICE_PITCH] [--proxy PROXY]
               [--break_duration BREAK_DURATION]
               input_file output_folder

Convert text book to audiobook

positional arguments:
  input_file            Path to the EPUB file
  output_folder         Path to the output folder

options:
  -h, --help            show this help message and exit
  --tts {azure,openai,edge}
                        Choose TTS provider (default: azure). azure: Azure
                        Cognitive Services, openai: OpenAI TTS API. When using
                        azure, environment variables MS_TTS_KEY and
                        MS_TTS_REGION must be set. When using openai,
                        environment variable OPENAI_API_KEY must be set.
  --log {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Log level (default: INFO), can be DEBUG, INFO,
                        WARNING, ERROR, CRITICAL
  --preview             Enable preview mode. In preview mode, the script will
                        not convert the text to speech. Instead, it will print
                        the chapter index, titles, and character counts.
  --no_prompt           Don't ask the user if they wish to continue after
                        estimating the cloud cost for TTS. Useful for
                        scripting.
  --language LANGUAGE   Language for the text-to-speech service (default: en-
                        US). For Azure TTS (--tts=azure), check
                        https://learn.microsoft.com/en-us/azure/ai-
                        services/speech-service/language-
                        support?tabs=tts#text-to-speech for supported
                        languages. For OpenAI TTS (--tts=openai), their API
                        detects the language automatically. But setting this
                        will also help on splitting the text into chunks with
                        different strategies in this tool, especially for
                        Chinese characters. For Chinese books, use zh-CN, zh-
                        TW, or zh-HK.
  --newline_mode {single,double,none}
                        Choose the mode of detecting new paragraphs: 'single',
                        'double', or 'none'. 'single' means a single newline
                        character, while 'double' means two consecutive
                        newline characters. 'none' means all newline
                        characters will be replace with blank so paragraphs
                        will not be detected. (default: double, works for most
                        ebooks but will detect less paragraphs for some
                        ebooks)
  --title_mode {auto,tag_text,first_few}
                        Choose the parse mode for chapter title, 'tag_text'
                        search 'title','h1','h2','h3' tag for title,
                        'first_few' set first 60 characters as title, 'auto'
                        auto apply the best mode for current chapter.
  --chapter_start CHAPTER_START
                        Chapter start index (default: 1, starting from 1)
  --chapter_end CHAPTER_END
                        Chapter end index (default: -1, meaning to the last
                        chapter)
  --output_text         Enable Output Text. This will export a plain text file
                        for each chapter specified and write the files to the
                        output folder specified.
  --remove_endnotes     This will remove endnote numbers from the end or
                        middle of sentences. This is useful for academic
                        books.
  --voice_name VOICE_NAME
                        Various TTS providers has different voice names, look
                        up for your provider settings.
  --output_format OUTPUT_FORMAT
                        Output format for the text-to-speech service.
                        Supported format depends on selected TTS provider
  --model_name MODEL_NAME
                        Various TTS providers has different neural model names

edge specific:
  --voice_rate VOICE_RATE
                        Speaking rate of the text. Valid relative values range
                        from -50%(--xxx='-50%') to +100%. For negative value
                        use format --arg=value,
  --voice_volume VOICE_VOLUME
                        Volume level of the speaking voice. Valid relative
                        values floor to -100%. For negative value use format
                        --arg=value,
  --voice_pitch VOICE_PITCH
                        Baseline pitch for the text.Valid relative values like
                        -80Hz,+50Hz, pitch changes should be within 0.5 to 1.5
                        times the original audio. For negative value use
                        format --arg=value,
  --proxy PROXY         Proxy server for the TTS provider. Format:
                        http://[username:password@]proxy.server:port

azure/edge specific:
  --break_duration BREAK_DURATION
                        Break duration in milliseconds for the different
                        paragraphs or sections (default: 1250, means 1.25 s).
                        Valid values range from 0 to 5000 milliseconds for
                        Azure TTS.
```

**Example**:

```bash
python3 main.py examples/The_Life_and_Adventures_of_Robinson_Crusoe.epub output_folder
```

Executing the above command will generate a directory named `output_folder` and save the MP3 files for each chapter inside it using default TTS provider and voice. Once generated, you can import these audio files into [Audiobookshelf](https://github.com/advplyr/audiobookshelf) or play them with any audio player of your choice.

## Preview Mode

Before converting your epub file to an audiobook, you can use the `--preview` option to get a summary of each chapter. This will provide you with the character count of each chapter and the total count, instead of converting the text to speech.

**Example**:

```bash
python3 main.py examples/The_Life_and_Adventures_of_Robinson_Crusoe.epub output_folder --preview
```

## Using with Docker

This tool is available as a Docker image, making it easy to run without needing to manage Python dependencies.

First, make sure you have Docker installed on your system.

You can pull the Docker image from the GitHub Container Registry:

```bash
docker pull ghcr.io/p0n1/epub_to_audiobook:latest
```

Then, you can run the tool with the following command:

```bash
docker run -i -t --rm -v ./:/app -e MS_TTS_KEY=$MS_TTS_KEY -e MS_TTS_REGION=$MS_TTS_REGION ghcr.io/p0n1/epub_to_audiobook your_book.epub audiobook_output --tts azure
```

For OpenAI, you can run:

```bash
docker run -i -t --rm -v ./:/app -e OPENAI_API_KEY=$OPENAI_API_KEY ghcr.io/p0n1/epub_to_audiobook your_book.epub audiobook_output --tts openai
```

Replace `$MS_TTS_KEY` and `$MS_TTS_REGION` with your Azure Text-to-Speech API credentials. Replace `$OPENAI_API_KEY` with your OpenAI API key. Replace `your_book.epub` with the name of the input EPUB file, and `audiobook_output` with the name of the directory where you want to save the output files.

The `-v ./:/app` option mounts the current directory (`.`) to the `/app` directory in the Docker container. This allows the tool to read the input file and write the output files to your local file system.

The `-i` and `-t` options are required to enable interactive mode and allocate a pseudo-TTY.

**You can also check the [this example config file](./docker-compose.example.yml) for docker compose usage.**

## User-Friendly Guide for Windows Users

For Windows users, especially if you're not very familiar with command-line tools, we've got you covered. We understand the challenges and have created a guide specifically tailored for you.

Check this [step by step guide](https://gist.github.com/p0n1/cba98859cdb6331cc1aab835d62e4fba) and leave a message if you encounter issues.

## How to Get Your Azure Cognitive Service Key?

- Azure subscription - [Create one for free](https://azure.microsoft.com/free/cognitive-services)
- [Create a Speech resource](https://portal.azure.com/#create/Microsoft.CognitiveServicesSpeechServices) in the Azure portal.
- Get the Speech resource key and region. After your Speech resource is deployed, select **Go to resource** to view and manage keys. For more information about Cognitive Services resources, see [Get the keys for your resource](https://learn.microsoft.com/en-us/azure/cognitive-services/cognitive-services-apis-create-account#get-the-keys-for-your-resource).

*Source: <https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/get-started-text-to-speech#prerequisites>*

## How to Get Your OpenAI API Key?

Check https://platform.openai.com/docs/quickstart/account-setup. Make sure you check the [price](https://openai.com/pricing) details before use.

## ✨ About Edge TTS

Edge TTS and Azure TTS are almost same, the difference is that Edge TTS don't require API Key because it's based on Edge read aloud functionality, and parameters are restricted a bit, like [custom ssml](https://github.com/rany2/edge-tts#custom-ssml).

Check https://gist.github.com/BettyJJ/17cbaa1de96235a7f5773b8690a20462 for supported voices.

**If you want to try this project quickly, Edge TTS is highly recommended.**

## Customization of Voice and Language

You can customize the voice and language used for the Text-to-Speech conversion by passing the `--voice_name` and `--language` options when running the script.

Microsoft Azure offers a range of voices and languages for the Text-to-Speech service. For a list of available options, consult the [Microsoft Azure Text-to-Speech documentation](https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support?tabs=tts#text-to-speech).

You can also listen to samples of the available voices in the [Azure TTS Voice Gallery](https://aka.ms/speechstudio/voicegallery) to help you choose the best voice for your audiobook.

For example, if you want to use a British English female voice for the conversion, you can use the following command:

```bash
python3 main.py <input_file> <output_folder> --voice_name en-GB-LibbyNeural --language en-GB
```

For OpenAI TTS, you can specify the model, voice, and format options using `--model_name`, `--voice_name`, and `--output_format`, respectively.

## More examples

Here are some examples that demonstrate various option combinations:

### Examples Using Azure TTS

1. **Basic conversion using Azure with default settings**  
   This command will convert an EPUB file to an audiobook using Azure's default TTS settings.

   ```sh
   python3 main.py "path/to/book.epub" "path/to/output/folder" --tts azure
   ```

2. **Azure conversion with custom language, voice and logging level**  
   Converts an EPUB file to an audiobook with a specified voice and a custom log level for debugging purposes.

   ```sh
   python3 main.py "path/to/book.epub" "path/to/output/folder" --tts azure --language zh-CN --voice_name "zh-CN-YunyeNeural" --log DEBUG
   ```

3. **Azure conversion with chapter range and break duration**  
   Converts a specified range of chapters from an EPUB file to an audiobook with custom break duration between paragraphs.

   ```sh
   python3 main.py "path/to/book.epub" "path/to/output/folder" --tts azure --chapter_start 5 --chapter_end 10 --break_duration "1500"
   ```

### Examples Using OpenAI TTS

1. **Basic conversion using OpenAI with default settings**  
   This command will convert an EPUB file to an audiobook using OpenAI's default TTS settings.

   ```sh
   python3 main.py "path/to/book.epub" "path/to/output/folder" --tts openai
   ```

2. **OpenAI conversion with HD model and specific voice**  
   Converts an EPUB file to an audiobook using the high-definition OpenAI model and a specific voice choice.

   ```sh
   python3 main.py "path/to/book.epub" "path/to/output/folder" --tts openai --model_name "tts-1-hd" --voice_name "fable"
   ```

3. **OpenAI conversion with preview and text output**  
   Enables preview mode and text output, which will display the chapter index and titles instead of converting them and will also export the text.

   ```sh
   python3 main.py "path/to/book.epub" "path/to/output/folder" --tts openai --preview --output_text
   ```

### Examples Using Edge TTS

1. **Basic conversion using Edge with default settings**  
   This command will convert an EPUB file to an audiobook using Edge's default TTS settings.

   ```sh
   python3 main.py "path/to/book.epub" "path/to/output/folder" --tts edge
   ```

2. **Edge conversion with custom language, voice and logging level**
   Converts an EPUB file to an audiobook with a specified voice and a custom log level for debugging purposes.

   ```sh
   python3 main.py "path/to/book.epub" "path/to/output/folder" --tts edge --language zh-CN --voice_name "zh-CN-YunxiNeural" --log DEBUG
   ```

3. **Edge conversion with chapter range and break duration**
   Converts a specified range of chapters from an EPUB file to an audiobook with custom break duration between paragraphs.

   ```sh
   python3 main.py "path/to/book.epub" "path/to/output/folder" --tts edge --chapter_start 5 --chapter_end 10 --break_duration "1500"
   ```

## Troubleshooting

### ModuleNotFoundError: No module named 'importlib_metadata'

This may be because the Python version you are using is [less than 3.8](https://stackoverflow.com/questions/73165636/no-module-named-importlib-metadata). You can try to manually install it by `pip3 install importlib-metadata`, or use a higher Python version.

### FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'

Make sure ffmpeg biary is accessible from your path. If you are on a mac and use homebrew, you can do `brew install ffmpeg`, On Ubuntu you can do `sudo apt install ffmpeg`


## Related Projects

- [Epub to Audiobook (M4B)](https://github.com/duplaja/epub-to-audiobook-hf): Epub to MB4 Audiobook, with StyleTTS2 via HuggingFace Spaces API.
- [Storyteller](https://smoores.gitlab.io/storyteller/): A self-hosted platform for automatically syncing ebooks and audiobooks.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

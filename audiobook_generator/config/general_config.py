class GeneralConfig:
    def __init__(self, args):
        # General arguments
        self.input_file = args.input_file
        self.output_folder = args.output_folder
        self.preview = args.preview
        self.output_text = args.output_text
        self.log = args.log
        self.no_prompt = args.no_prompt
        self.title_mode = args.title_mode
        self.test_mode = args.test_mode

        # Book parser specific arguments
        self.newline_mode = args.newline_mode
        self.chapter_start = args.chapter_start
        self.chapter_end = args.chapter_end
        self.remove_endnotes = args.remove_endnotes
        self.fnote_transplant = args.fnote_transplant

        # TTS provider: common arguments
        self.tts = args.tts
        self.language = args.language
        self.voice_name = args.voice_name
        self.output_format = args.output_format
        self.model_name = args.model_name

        # TTS provider: Azure & Edge TTS specific arguments
        self.break_duration = args.break_duration

        # TTS provider: Edge specific arguments
        self.voice_rate = args.voice_rate
        self.voice_volume = args.voice_volume
        self.voice_pitch = args.voice_pitch
        self.proxy = args.proxy

        # TTS provider: OpenAI TTS Provider
        self.ttsfm = args.ttsfm
        self.instructions = args.instructions

        self.sum_url = args.sum_url
        self.sum_api = args.sum_api
        self.sum_model = args.sum_model
        self.sum_only = args.sum_only

    def __str__(self):
        return ', '.join(f"{key}={value}" for key, value in self.__dict__.items())

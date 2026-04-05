"""
VII Two — Text cleaning and sentence extraction for TTS.
Ported from DecisionsAI's LLM service patterns.

Cleans LLM output for natural speech and splits into sentences
for streaming TTS generation.
"""

import re
import logging
from .processor import FrameProcessor
from .frames import Frame, TextFrame, SentenceFrame

logger = logging.getLogger("vii.pipeline.text_cleaner")

# Smart quotes → straight quotes (critical for Kokoro phonemization)
_SMART_QUOTES = re.compile(r'[\u2018\u2019\u201A\u201B]')
_SMART_DOUBLE = re.compile(r'[\u201C\u201D\u201E\u201F]')

# Markdown artifacts
_MARKDOWN_BOLD = re.compile(r'\*\*(.+?)\*\*')
_MARKDOWN_ITALIC = re.compile(r'\*(.+?)\*')
_MARKDOWN_CODE = re.compile(r'`(.+?)`')
_MARKDOWN_HEADER = re.compile(r'^#{1,6}\s+', re.MULTILINE)
_MARKDOWN_LIST = re.compile(r'^\s*[-*]\s+', re.MULTILINE)
_MARKDOWN_LINK = re.compile(r'\[(.+?)\]\(.+?\)')

# Sentence-ending punctuation (handles decimals & versions)
# "Dr. Smith" won't split. "v2.1.3" won't split. "Hello. World" will.
_SENTENCE_END = re.compile(
    r'(?<!\b(?:Dr|Mr|Mrs|Ms|Prof|Sr|Jr|vs|etc|approx|dept|est|govt|inc))'
    r'(?<!\d)'
    r'[.!?]'
    r'(?=\s+[A-Z"\']|\s*$)'
)

# Max chars per TTS chunk (Kokoro has issues above ~390)
MAX_TTS_CHARS = 380


def clean_text_for_tts(text: str) -> str:
    """Clean LLM output for natural speech synthesis."""
    # Smart quotes → straight
    text = _SMART_QUOTES.sub("'", text)
    text = _SMART_DOUBLE.sub('"', text)

    # Strip markdown
    text = _MARKDOWN_BOLD.sub(r'\1', text)
    text = _MARKDOWN_ITALIC.sub(r'\1', text)
    text = _MARKDOWN_CODE.sub(r'\1', text)
    text = _MARKDOWN_HEADER.sub('', text)
    text = _MARKDOWN_LIST.sub('', text)
    text = _MARKDOWN_LINK.sub(r'\1', text)

    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def extract_complete_sentences(text: str) -> tuple[list[str], str]:
    """
    Extract complete sentences from accumulated text.
    Returns (complete_sentences, remaining_text).

    Handles:
    - Decimal numbers ("version 2.1.3")
    - Abbreviations ("Dr. Smith")
    - Long sentences (split at commas if > MAX_TTS_CHARS)
    """
    sentences = []
    remaining = text

    for match in _SENTENCE_END.finditer(text):
        end_pos = match.end()
        sentence = text[:end_pos].strip()

        if sentence:
            # Split long sentences at commas/semicolons
            if len(sentence) > MAX_TTS_CHARS:
                sub_sentences = _split_long_sentence(sentence)
                sentences.extend(sub_sentences)
            else:
                sentences.append(sentence)

        text = text[end_pos:].strip()

    remaining = text
    return sentences, remaining


def _split_long_sentence(text: str) -> list[str]:
    """Split a long sentence at natural break points."""
    parts = []
    while len(text) > MAX_TTS_CHARS:
        # Find last comma or semicolon before limit
        split_pos = -1
        for sep in ['; ', ', ', ' — ', ' - ']:
            pos = text.rfind(sep, 0, MAX_TTS_CHARS)
            if pos > split_pos:
                split_pos = pos + len(sep)

        if split_pos <= 0:
            # No good break point — split at word boundary
            split_pos = text.rfind(' ', 0, MAX_TTS_CHARS)
            if split_pos <= 0:
                split_pos = MAX_TTS_CHARS

        parts.append(text[:split_pos].strip())
        text = text[split_pos:].strip()

    if text:
        parts.append(text)

    return parts


class TextCleaner(FrameProcessor):
    """
    Pipeline processor: accumulates LLM text tokens,
    cleans them, extracts complete sentences, and pushes
    SentenceFrames downstream to TTS.
    """

    def __init__(self):
        super().__init__(name="TextCleaner")
        self._buffer = ""
        self._sentence_index = 0

    async def process_frame(self, frame: Frame):
        if isinstance(frame, TextFrame):
            # Accumulate and clean
            cleaned = clean_text_for_tts(frame.text)
            self._buffer += cleaned

            # Extract complete sentences
            sentences, self._buffer = extract_complete_sentences(self._buffer)

            for sentence in sentences:
                if sentence.strip():
                    await self.push_frame(SentenceFrame(
                        text=sentence,
                        sentence_index=self._sentence_index,
                    ))
                    self._sentence_index += 1
        else:
            # Pass through non-text frames (control, lifecycle)
            await self.push_frame(frame)

    def flush(self) -> str:
        """Flush remaining buffer (call at end of LLM response)."""
        remaining = self._buffer.strip()
        self._buffer = ""
        self._sentence_index = 0
        return remaining

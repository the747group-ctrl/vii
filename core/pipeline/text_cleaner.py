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
# Uses a simpler approach compatible with Python 3.14's strict lookbehind rules
_ABBREVIATIONS = {'Dr', 'Mr', 'Mrs', 'Ms', 'Prof', 'Sr', 'Jr', 'vs', 'etc', 'approx', 'dept', 'est', 'govt', 'inc'}

def _is_sentence_end(text: str, pos: int) -> bool:
    """Check if a period/!/?  at position pos is a real sentence end."""
    if pos >= len(text):
        return False
    char = text[pos]
    if char not in '.!?':
        return False
    # Check what follows: must be whitespace + uppercase, or end of string
    rest = text[pos+1:]
    if not rest or rest == ' ':
        return True
    if rest[0] in ' \t\n':
        remaining = rest.lstrip()
        if not remaining:
            return True
        if remaining[0].isupper() or remaining[0] in '"\'':
            # Check what's before — is it an abbreviation?
            before = text[:pos].rstrip()
            last_word = before.split()[-1] if before.split() else ''
            if last_word in _ABBREVIATIONS:
                return False
            # Check if preceded by a digit (decimal number)
            if before and before[-1].isdigit():
                return False
            return True
    return False

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
    last_split = 0

    for i, char in enumerate(text):
        if char in '.!?' and _is_sentence_end(text, i):
            sentence = text[last_split:i+1].strip()
            if sentence:
                if len(sentence) > MAX_TTS_CHARS:
                    sentences.extend(_split_long_sentence(sentence))
                else:
                    sentences.append(sentence)
            last_split = i + 1

    remaining = text[last_split:].strip() if last_split < len(text) else ""
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

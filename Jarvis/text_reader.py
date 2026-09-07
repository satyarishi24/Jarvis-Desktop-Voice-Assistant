"""Core text-to-speech engine used by the Read Aloud app.

Wraps pyttsx3 in a worker thread so the caller (GUI or CLI) stays responsive and
can stop, pause or resume playback while text is being spoken.

pyttsx3 itself has no pause primitive, so pausing is done at chunk boundaries:
the text is split into sentence sized chunks and the worker waits before
starting the next chunk.
"""

import os
import re
import threading


# Chunks longer than this are split further so stop/pause stay responsive.
MAX_CHUNK_CHARS = 240

_SENTENCE_END = re.compile(r"(?<=[.!?;:])\s+|\n+")


def split_into_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list:
    """Splits text into speakable chunks, roughly one sentence each."""
    chunks = []
    for piece in _SENTENCE_END.split(text or ""):
        piece = piece.strip()
        if not piece:
            continue

        while len(piece) > max_chars:
            # Break on the last space before the limit, else hard split.
            cut = piece.rfind(" ", 0, max_chars)
            if cut <= 0:
                cut = max_chars
            chunks.append(piece[:cut].strip())
            piece = piece[cut:].strip()

        if piece:
            chunks.append(piece)

    return chunks


def read_text_file(path: str) -> str:
    """Reads a plain text file, falling back to a lenient decode."""
    try:
        with open(path, "r", encoding="utf-8") as file:
            return file.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="utf-8", errors="replace") as file:
            return file.read()


class TextReader:
    """Speaks text out loud with stop, pause and resume support."""

    def __init__(self, rate=170, volume=1.0, voice=None):
        import pyttsx3  # imported lazily so --help works without audio deps

        self.engine = pyttsx3.init()
        self._lock = threading.Lock()
        self._thread = None
        self._stop_flag = threading.Event()
        self._resume_flag = threading.Event()
        self._resume_flag.set()

        self.set_rate(rate)
        self.set_volume(volume)
        if voice is not None:
            self.set_voice(voice)

    # ------------------------------------------------------------------
    # Voice settings
    # ------------------------------------------------------------------
    def list_voices(self) -> list:
        """Returns the available voices as (index, name, id) tuples."""
        voices = self.engine.getProperty("voices")
        return [(i, getattr(v, "name", "unknown"), v.id) for i, v in enumerate(voices)]

    def set_voice(self, voice) -> None:
        """Selects a voice by index, exact id, or case insensitive name."""
        voices = self.engine.getProperty("voices")
        if not voices:
            return

        if isinstance(voice, int):
            self.engine.setProperty("voice", voices[voice % len(voices)].id)
            return

        wanted = str(voice).strip()
        if wanted.lstrip("-").isdigit():
            self.engine.setProperty("voice", voices[int(wanted) % len(voices)].id)
            return

        for entry in voices:
            name = getattr(entry, "name", "") or ""
            if entry.id == wanted or name.lower() == wanted.lower():
                self.engine.setProperty("voice", entry.id)
                return

        for entry in voices:
            name = getattr(entry, "name", "") or ""
            if wanted.lower() in name.lower():
                self.engine.setProperty("voice", entry.id)
                return

        raise ValueError(f"No voice matching {voice!r}")

    def set_rate(self, rate) -> None:
        """Sets speaking speed in words per minute."""
        self.engine.setProperty("rate", int(rate))

    def set_volume(self, volume) -> None:
        """Sets volume in the 0.0 to 1.0 range."""
        self.engine.setProperty("volume", max(0.0, min(1.0, float(volume))))

    @property
    def rate(self) -> int:
        return int(self.engine.getProperty("rate"))

    @property
    def volume(self) -> float:
        return float(self.engine.getProperty("volume"))

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------
    def is_speaking(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def is_paused(self) -> bool:
        return self.is_speaking() and not self._resume_flag.is_set()

    def speak(self, text: str, on_chunk=None, on_finish=None) -> None:
        """Speaks text on a worker thread and returns immediately.

        on_chunk(index, total, chunk) is called before each chunk is spoken and
        on_finish(completed) once playback ends, where completed is False if it
        was stopped early.
        """
        self.stop()

        chunks = split_into_chunks(text)
        if not chunks:
            if on_finish:
                on_finish(True)
            return

        self._stop_flag.clear()
        self._resume_flag.set()
        self._thread = threading.Thread(
            target=self._run, args=(chunks, on_chunk, on_finish), daemon=True
        )
        self._thread.start()

    def speak_blocking(self, text: str, on_chunk=None) -> bool:
        """Speaks text and waits for it to finish. Returns False if stopped."""
        result = {}
        self.speak(text, on_chunk=on_chunk, on_finish=lambda done: result.update(done=done))
        self.wait()
        return result.get("done", False)

    def _run(self, chunks, on_chunk, on_finish) -> None:
        completed = True
        try:
            for index, chunk in enumerate(chunks):
                # Block here while paused, but keep reacting to stop.
                while not self._resume_flag.wait(timeout=0.1):
                    if self._stop_flag.is_set():
                        break

                if self._stop_flag.is_set():
                    completed = False
                    break

                if on_chunk:
                    on_chunk(index, len(chunks), chunk)

                with self._lock:
                    self.engine.say(chunk)
                    self.engine.runAndWait()
        finally:
            if on_finish:
                on_finish(completed)

    def pause(self) -> None:
        """Pauses playback once the current sentence finishes."""
        self._resume_flag.clear()

    def resume(self) -> None:
        """Resumes playback after a pause."""
        self._resume_flag.set()

    def toggle_pause(self) -> bool:
        """Flips pause state and returns True if now paused."""
        if self.is_paused():
            self.resume()
            return False
        self.pause()
        return True

    def stop(self) -> None:
        """Stops playback and waits for the worker thread to exit."""
        if not self.is_speaking():
            self._stop_flag.clear()
            self._resume_flag.set()
            return

        self._stop_flag.set()
        self._resume_flag.set()
        try:
            self.engine.stop()
        except Exception:
            pass

        self._thread.join(timeout=5)
        self._thread = None

    def wait(self) -> None:
        """Blocks until the current text has been read."""
        if self._thread is not None:
            self._thread.join()

    # ------------------------------------------------------------------
    # File output
    # ------------------------------------------------------------------
    def save_to_file(self, text: str, path: str) -> str:
        """Renders text to an audio file instead of the speakers."""
        self.stop()
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)

        with self._lock:
            self.engine.save_to_file(text, path)
            self.engine.runAndWait()
        return path

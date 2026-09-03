"""Speech in and speech out, both optional.

Every dependency here is soft: if a microphone, a speaker or the packages are
missing, Jarvis falls back to the keyboard and says so once instead of crashing.
"""

from __future__ import annotations

from typing import Optional


class Voice:
    """Text-to-speech and speech-to-text, each degrading to silence."""

    def __init__(self, speak_enabled: bool = True, listen_enabled: bool = False) -> None:
        self.speak_enabled = speak_enabled
        self.listen_enabled = listen_enabled
        self._engine = None
        self._recognizer = None
        self._microphone = None
        self.notes: list[str] = []

        if speak_enabled:
            self._setup_speech()
        if listen_enabled:
            self._setup_hearing()

    # -- output ----------------------------------------------------------

    def _setup_speech(self) -> None:
        try:
            import pyttsx3  # type: ignore

            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.setProperty("volume", 1.0)
            self._engine = engine
        except Exception as exc:
            self.speak_enabled = False
            self.notes.append(f"Voice output is off ({exc}).")

    def speak(self, text: str) -> None:
        """Say something out loud. A no-op when speech is unavailable."""
        if not self.speak_enabled or self._engine is None or not text.strip():
            return
        try:
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception:
            # A failing TTS engine must never take the assistant down with it.
            self.speak_enabled = False

    # -- input -----------------------------------------------------------

    def _setup_hearing(self) -> None:
        try:
            import speech_recognition as sr  # type: ignore

            self._recognizer = sr.Recognizer()
            self._recognizer.pause_threshold = 0.8
            self._microphone = sr.Microphone()
        except Exception as exc:
            self.listen_enabled = False
            self.notes.append(f"Voice input is off ({exc}). Type your requests instead.")

    def listen(self, timeout: int = 8, phrase_limit: int = 20) -> Optional[str]:
        """Capture one spoken phrase. Returns None if nothing usable was heard."""
        if not self.listen_enabled or self._recognizer is None or self._microphone is None:
            return None

        import speech_recognition as sr  # type: ignore

        try:
            with self._microphone as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.4)
                audio = self._recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_limit
                )
        except sr.WaitTimeoutError:
            return None
        except Exception:
            return None

        try:
            return self._recognizer.recognize_google(audio, language="en-in")
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            self.notes.append("Speech recognition service unreachable; switching to typing.")
            self.listen_enabled = False
            return None

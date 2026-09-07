"""Read Aloud: a small app that reads text out loud.

Two ways to use it:

    python Jarvis/read_aloud.py                        # desktop window
    python Jarvis/read_aloud.py --text "hello there"   # command line
    python Jarvis/read_aloud.py --file notes.txt --save notes.wav

The speech engine lives in text_reader.py; this file is the user interface.
"""

import argparse
import os
import sys

try:  # allow running as a script or importing as part of the package
    from Jarvis.text_reader import TextReader, read_text_file
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from text_reader import TextReader, read_text_file


DEFAULT_RATE = 170
DEFAULT_VOLUME = 1.0


# ----------------------------------------------------------------------
# Command line mode
# ----------------------------------------------------------------------
def collect_text(args) -> str:
    """Builds the text to read from the command line arguments."""
    if args.text:
        return args.text
    if args.file:
        return read_text_file(args.file)
    if args.stdin or not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def run_cli(args) -> int:
    reader = TextReader(rate=args.rate, volume=args.volume, voice=args.voice)

    if args.list_voices:
        for index, name, voice_id in reader.list_voices():
            print(f"{index}: {name}  [{voice_id}]")
        return 0

    text = collect_text(args).strip()
    if not text:
        print("Nothing to read. Pass --text, --file, or pipe text in.", file=sys.stderr)
        return 1

    if args.save:
        path = reader.save_to_file(text, args.save)
        print(f"Saved audio to {path}")
        return 0

    def show(index, total, chunk):
        if args.verbose:
            print(f"[{index + 1}/{total}] {chunk}")

    reader.speak_blocking(text, on_chunk=show)
    return 0


# ----------------------------------------------------------------------
# Desktop window mode
# ----------------------------------------------------------------------
def run_gui(args) -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    reader = TextReader(rate=args.rate, volume=args.volume, voice=args.voice)
    voices = reader.list_voices()

    root = tk.Tk()
    root.title("Read Aloud")
    root.geometry("760x560")
    root.minsize(560, 420)

    status = tk.StringVar(value="Type or open a file, then press Speak.")

    # --- text area -----------------------------------------------------
    text_frame = tk.Frame(root)
    text_frame.pack(fill="both", expand=True, padx=10, pady=(10, 6))

    text_box = tk.Text(text_frame, wrap="word", font=("Segoe UI", 11), undo=True)
    scrollbar = tk.Scrollbar(text_frame, command=text_box.yview)
    text_box.configure(yscrollcommand=scrollbar.set)
    text_box.tag_configure("speaking", background="#ffe58a")
    scrollbar.pack(side="right", fill="y")
    text_box.pack(side="left", fill="both", expand=True)

    # --- voice settings -------------------------------------------------
    settings = tk.Frame(root)
    settings.pack(fill="x", padx=10)

    tk.Label(settings, text="Voice").grid(row=0, column=0, sticky="w", padx=(0, 6))
    voice_names = [f"{i}: {name}" for i, name, _ in voices] or ["default"]
    voice_choice = ttk.Combobox(settings, values=voice_names, state="readonly", width=34)
    voice_choice.current(0)
    voice_choice.grid(row=0, column=1, sticky="w")

    def on_voice(_event=None):
        if voices:
            reader.set_voice(voices[voice_choice.current()][0])

    voice_choice.bind("<<ComboboxSelected>>", on_voice)

    tk.Label(settings, text="Speed").grid(row=0, column=2, sticky="e", padx=(16, 4))
    rate_slider = tk.Scale(
        settings, from_=80, to=320, orient="horizontal", length=160, showvalue=True,
        command=lambda value: reader.set_rate(float(value)),
    )
    rate_slider.set(reader.rate)
    rate_slider.grid(row=0, column=3, sticky="w")

    tk.Label(settings, text="Volume").grid(row=0, column=4, sticky="e", padx=(16, 4))
    volume_slider = tk.Scale(
        settings, from_=0, to=100, orient="horizontal", length=120, showvalue=True,
        command=lambda value: reader.set_volume(float(value) / 100.0),
    )
    volume_slider.set(int(reader.volume * 100))
    volume_slider.grid(row=0, column=5, sticky="w")

    # --- playback helpers ------------------------------------------------
    pause_button = None  # assigned below, referenced by the callbacks

    def current_text() -> str:
        return text_box.get("1.0", "end-1c")

    # Where the highlight search resumes, so repeated sentences advance.
    search_from = ["1.0"]

    def highlight(chunk: str) -> None:
        text_box.tag_remove("speaking", "1.0", "end")
        needle = chunk[:80]
        start = text_box.search(needle, search_from[0], stopindex="end")
        if not start:
            start = text_box.search(needle, "1.0", stopindex="end")
        if start:
            end = f"{start}+{len(chunk)}c"
            text_box.tag_add("speaking", start, end)
            text_box.see(start)
            search_from[0] = end

    def on_chunk(index, total, chunk):
        root.after(0, lambda: (status.set(f"Reading sentence {index + 1} of {total}"),
                               highlight(chunk)))

    def on_finish(completed):
        def done():
            text_box.tag_remove("speaking", "1.0", "end")
            pause_button.config(text="Pause")
            status.set("Finished reading." if completed else "Stopped.")
        root.after(0, done)

    def do_speak():
        text = current_text().strip()
        if not text:
            status.set("There is no text to read.")
            return
        pause_button.config(text="Pause")
        search_from[0] = "1.0"
        status.set("Reading...")
        reader.speak(text, on_chunk=on_chunk, on_finish=on_finish)

    def do_pause():
        if not reader.is_speaking():
            return
        paused = reader.toggle_pause()
        pause_button.config(text="Resume" if paused else "Pause")
        status.set("Paused after the current sentence." if paused else "Reading...")

    def do_stop():
        reader.stop()
        text_box.tag_remove("speaking", "1.0", "end")
        pause_button.config(text="Pause")
        status.set("Stopped.")

    def do_open():
        path = filedialog.askopenfilename(
            title="Open a text file",
            filetypes=[("Text files", "*.txt *.md *.log *.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            content = read_text_file(path)
        except OSError as error:
            messagebox.showerror("Read Aloud", f"Could not open the file:\n{error}")
            return
        do_stop()
        text_box.delete("1.0", "end")
        text_box.insert("1.0", content)
        status.set(f"Loaded {os.path.basename(path)}")

    def do_save_audio():
        text = current_text().strip()
        if not text:
            status.set("There is no text to save.")
            return
        path = filedialog.asksaveasfilename(
            title="Save spoken audio",
            defaultextension=".wav",
            filetypes=[("WAV audio", "*.wav"), ("All files", "*.*")],
        )
        if not path:
            return
        status.set("Saving audio...")
        root.update_idletasks()
        try:
            reader.save_to_file(text, path)
        except Exception as error:
            messagebox.showerror("Read Aloud", f"Could not save the audio:\n{error}")
            status.set("Saving failed.")
            return
        status.set(f"Saved audio to {path}")

    def do_clear():
        do_stop()
        text_box.delete("1.0", "end")
        status.set("Cleared.")

    # --- buttons ---------------------------------------------------------
    buttons = tk.Frame(root)
    buttons.pack(fill="x", padx=10, pady=8)

    tk.Button(buttons, text="Speak", width=12, command=do_speak).pack(side="left")
    pause_button = tk.Button(buttons, text="Pause", width=12, command=do_pause)
    pause_button.pack(side="left", padx=6)
    tk.Button(buttons, text="Stop", width=12, command=do_stop).pack(side="left")
    tk.Button(buttons, text="Open File", width=12, command=do_open).pack(side="left", padx=6)
    tk.Button(buttons, text="Save as WAV", width=12, command=do_save_audio).pack(side="left")
    tk.Button(buttons, text="Clear", width=10, command=do_clear).pack(side="left", padx=6)

    tk.Label(root, textvariable=status, anchor="w", relief="sunken", padx=6).pack(
        fill="x", side="bottom"
    )

    root.bind("<Control-Return>", lambda _e: do_speak())
    root.bind("<Control-space>", lambda _e: do_pause())
    root.bind("<Escape>", lambda _e: do_stop())
    root.bind("<Control-o>", lambda _e: do_open())

    if args.file:
        try:
            text_box.insert("1.0", read_text_file(args.file))
            status.set(f"Loaded {os.path.basename(args.file)}")
        except OSError as error:
            status.set(f"Could not open {args.file}: {error}")
    elif args.text:
        text_box.insert("1.0", args.text)

    def on_close():
        reader.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
    return 0


# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="read_aloud",
        description="Read text out loud. Runs a desktop window by default.",
    )
    parser.add_argument("--text", help="text to read")
    parser.add_argument("--file", help="path to a text file to read")
    parser.add_argument("--stdin", action="store_true", help="read the text from stdin")
    parser.add_argument("--save", metavar="PATH", help="write the speech to a WAV file instead of playing it")
    parser.add_argument("--voice", help="voice index, name, or id (see --list-voices)")
    parser.add_argument("--list-voices", action="store_true", help="list the installed voices and exit")
    parser.add_argument("--rate", type=int, default=DEFAULT_RATE, help="speaking speed in words per minute")
    parser.add_argument("--volume", type=float, default=DEFAULT_VOLUME, help="volume from 0.0 to 1.0")
    parser.add_argument("--gui", action="store_true", help="force the desktop window")
    parser.add_argument("--no-gui", dest="gui_off", action="store_true", help="force command line mode")
    parser.add_argument("-v", "--verbose", action="store_true", help="print each sentence as it is spoken")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    piped = not sys.stdin.isatty()
    wants_cli = (args.gui_off or args.list_voices or args.save
                 or args.text or args.stdin or piped)
    if args.gui or not wants_cli:
        try:
            return run_gui(args)
        except ImportError:
            print("tkinter is not available, falling back to command line mode.", file=sys.stderr)

    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())

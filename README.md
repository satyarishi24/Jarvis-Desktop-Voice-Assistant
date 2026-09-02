# Jarvis Desktop Voice Assistant🔥

<img src="https://giffiles.alphacoders.com/212/212508.gif" alt="">

**Have you ever wondered how cool it would be to have your own assistant? Imagine how easier it would be doing Wikipedia searches without opening web browsers, and performing many other daily tasks like playing music with the help of a single voice command, opening different browsers in just a voice command.**

**This project is simple desktop voice assistant built with python named as “Jarvis Desktop Voice Assistant”. This project is fully completed and error free. It was compiled in VS Code Editor.**

**🔸 Let's be honest, it's not as intelligent as in the movie, but it can do a lot of cool things and automate your daily tasks you do on your personal computers/laptops.**

## 📌Built with

<code><img height="30" src="https://raw.githubusercontent.com/github/explore/80688e429a7d4ef2fca1e82350fe8e3517d3494d/topics/python/python.png"></code>

## 📌Features

It can do a lot of cool things, some of them being:

- Greet user
- Tell current time and date
- Launch applications/softwares
- Open any website
- Tells about any person (via Wikipedia)
- Can search anything on Google
- Plays music
- Take important note in text file
- Can take screenshot and save it with custom filename
- Can tell jokes

**And as of 2.0, a Claude-powered agent that can operate the whole machine —
files, shell, screen, apps and system — from a plain-language request.
See [Jarvis 2.0](#-jarvis-20--the-ai-assistant-that-actually-operates-your-device).**

## Requirements

Python 3.6+ for the original script, Python 3.10+ for the Claude-powered assistant.

## 📌Installation

1. **Fork The Repository**
   - Click the "Fork" button on the top right corner of the repository page.

2. **Clone The Repository**
   - Clone the forked repository to your local machine:
     ```bash
     git clone <URL>
     cd Jarvis-Desktop-Voice-Assistant
     ```

3.  **Create and Activate a Virtual Environment**
     - Create a virtual environment:
     ```bash
     python -m venv .venv
     ```
   - Activate the virtual environment:
     - For Windows:
       ```bash
       .venv\Scripts\activate
       ```
     - For macOS/Linux:
       ```bash
       source .venv/bin/activate
       ```
   - This activates the virtual environment and should look like `(venv) directory/of/your/project>`

4. **Install Requirements**

   - Install all the requirements given in **[requirements.txt](https://github.com/kishanrajput23/Jarvis-Desktop-Voice-Assistant/blob/main/requirements.txt)** by running the command `pip install -r requirements.txt`

5. **Install PyAudio**  
   - Follow the instructions given **[here](https://stackoverflow.com/questions/52283840/i-cant-install-pyaudio-on-windows-how-to-solve-error-microsoft-visual-c-14)**

6. **Run the Assistant**
  - Run the main script:
    ```bash
    python jarvis.py
    ```
  - Now Enjoy with your own assistant !!!!

7. **Deactivate the Virtual Environment**
   - After you're done, deactivate the virtual environment:
     ```bash
     deactivate
     ```

---

## 🤖 Jarvis 2.0 — the AI assistant that actually operates your device

The original `Jarvis/jarvis.py` matches keywords with an `if/elif` chain: it knows
`"open youtube"` and nothing else. `jarvis_ai/` replaces that with a **Claude-powered
agent**. You describe what you want in your own words, Claude picks and chains the
right device tools, and every action that changes your machine has to be approved
by you first.

```
you  find the invoice PDFs I downloaded last month and move them into ~/Documents/Invoices

  → find_files: search for files matching '*.pdf' under ~/Downloads
    12 matches for '*.pdf':
  → create_directory: create the directory ~/Documents/Invoices

  Jarvis wants to move ~/Downloads/invoice-april.pdf to ~/Documents/Invoices
  tool: move_path · modifies your machine
  Allow? [y/N] y

jarvis  Moved four invoices into Documents/Invoices. The other eight PDFs were
        receipts, so I left them where they were.
```

### What it can do

| Area | Tools |
|---|---|
| **Files** | list, read, write, find by name, search inside, copy, move, delete, inspect |
| **Shell** | run any command, start background processes, check what's installed |
| **System** | hardware and resource stats, processes, kill, network, shut down / restart / sleep / lock |
| **Screen** | take a screenshot **and look at it** — Claude reads your error dialogs |
| **Input** | type text, press keyboard shortcuts, control media keys and volume |
| **Apps** | launch applications, open files and folders, open websites, play music |
| **Clipboard** | read and write |
| **Web** | search the web (server-side, via Claude) |
| **Memory** | remember facts across sessions, take and read notes |

Anything not on that list still works through `run_command` — that is what makes
"does everything" literal rather than aspirational.

### Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...        # or run: ant auth login
python -m jarvis_ai
```

```bash
python -m jarvis_ai "how much disk space is left?"   # one-shot, then exit
python -m jarvis_ai --voice                          # talk to it instead of typing
python -m jarvis_ai --dry-run                        # show actions without doing them
```

Get an API key at [console.anthropic.com](https://console.anthropic.com/).
Python 3.10 or newer.

### Safety — read this part

The assistant can run shell commands on your machine, so it is built to fail
closed rather than fail fast:

- **Every action is rated.** Reads (`list_directory`, `system_info`) run freely.
  Writes (`write_file`, `launch_app`) and system-level actions (`run_command`,
  `delete_path`, `power_action`) stop and ask, showing you a plain-English
  description of what is about to happen.
- **Writes are fenced.** Nothing outside your home directory can be modified.
  Widen or narrow it with `--writable-root ~/projects`.
- **Credential files are guarded.** Reading anything matching `~/.ssh/*`,
  `.aws/credentials`, `*.env`, `*.pem` and friends needs explicit confirmation,
  even though reads are otherwise unrestricted.
- **Deletes go to the trash** when `send2trash` is installed.
- **A denial is final.** Claude is instructed to accept "no" and offer an
  alternative, never to retry the same action through a different tool.

| Flag | Effect |
|---|---|
| *(default)* | Ask before anything that changes the machine |
| `--dry-run` | Describe every action instead of performing it |
| `--read-only` | Refuse changes outright, without prompting |
| `--policy auto-edit` | Auto-approve file writes and app launches; still ask for shell, deletes and power |
| `--yolo` | Approve everything. Only sensible in a throwaway VM. |

### Configuration

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Your Claude API key |
| `JARVIS_MODEL` | Model to use (default `claude-opus-5`) |
| `JARVIS_EFFORT` | `low` … `max` — how hard Claude thinks before acting |
| `JARVIS_WRITABLE_ROOTS` | Path-separated list of directories it may modify |
| `JARVIS_DATA_DIR` | Where notes, memory and screenshots live (default `~/.jarvis`) |
| `JARVIS_COMMAND_TIMEOUT` | Seconds before a shell command is killed |
| `JARVIS_VOICE_INPUT` / `JARVIS_VOICE_OUTPUT` | Turn speech on or off |

### Adding a tool

Every capability is a decorated function. The JSON schema Claude sees is derived
from the signature, and the risk level decides whether it needs approval:

```python
@tool(
    risk=Risk.WRITE,
    description="Set the desktop wallpaper to an image file.",
    params={"path": "Image to use as the wallpaper."},
    preview=lambda path: f"set the wallpaper to {path}",
)
def set_wallpaper(ctx: ToolContext, path: str) -> str:
    ...
    return "Wallpaper changed."
```

Drop it in `jarvis_ai/tools/`, import it from `jarvis_ai/tools/__init__.py`, and
Claude can use it on the next run.

### Tests

```bash
python -m unittest discover tests
```

The suite covers the approval gate, the writable-root guard, tool dispatch, and
the agent loop (driven by a stubbed client, so it runs without an API key).

### The original script

`Jarvis/jarvis.py` is untouched and still works — it is a good, dependency-light
introduction to the idea. `jarvis_ai/` is where the intelligence lives.

---

## 📌Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## 📌Author

👤 **Kishan Kumar Rai**

- Twitter: [@kishan_rajput23](https://twitter.com/kishan_rajput23)
- Github: [@kishanrajput23](https://github.com/kishanrajput23)
- LinkedIn: [@kishan-kumar-rai](https://linkedin.com/in/kishan-kumar-rai-23112000)

## 📌Show your support

Please ⭐️ this repository if this project helped you!

## 📌License

This project is [MIT](https://choosealicense.com/licenses/mit/) licensed.

## 📌Learning Resources to Extend This Project

To build this project further and enhance its capabilities, a strong understanding of the following areas is recommended:

### 🐍 Python Fundamentals
Python is the core language behind this project. A solid grasp of syntax, control flow, functions, and error handling will help you modify and extend the assistant’s functionality.  
👉 [Python Programming Course](https://www.mygreatlearning.com/academy/premium/master-python-programming)

### 🎙️ Voice Processing & NLP
Voice commands are processed using speech and text-based techniques. Understanding Natural Language Processing (NLP) concepts such as tokenization and text analysis can help improve voice interaction.  
👉 [Introduction to NLP](https://www.mygreatlearning.com/academy/learn-for-free/courses/introduction-to-natural-language-processing)

### 🤖 Intelligence & Generative AI
Currently, the assistant follows predefined logic. By integrating Generative AI concepts, it can be enhanced into a conversational assistant capable of generating intelligent responses and performing web-based tasks.  
👉 [Introduction to Generative AI](https://www.mygreatlearning.com/academy/premium/master-generative-ai)

### 👁️ Computer Vision
To make the assistant more advanced, computer vision can be introduced for features like face detection and gesture control. Learning image and video processing fundamentals is a good starting point.  
👉 [Computer Vision Essentials](https://www.mygreatlearning.com/academy/learn-for-free/courses/computer-vision-essentials)

### 📄 Related Reading
For a conceptual overview of building voice assistants in Python, you can refer to this article: [CLICK HERE](https://www.mygreatlearning.com/blog/jarvis-desktop-assistant-python-project/)

---

> *Some learning resources mentioned above are shared as part of an educational collaboration.*

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

## 📌Read Aloud (Text-to-Speech App)

Along with the voice assistant, this repository ships a standalone app that reads
any text out loud: `Jarvis/read_aloud.py`. It uses the same offline `pyttsx3`
engine, so no internet connection or API key is needed.

**Desktop window**

```bash
python Jarvis/read_aloud.py
```

- Type or paste text, or open a `.txt`/`.md`/`.csv`/`.log` file
- Speak, Pause/Resume and Stop, with the sentence being read highlighted live
- Pick a voice, and adjust speed (80 to 320 wpm) and volume
- Save the spoken text to a WAV file
- Shortcuts: `Ctrl+Enter` speak, `Ctrl+Space` pause/resume, `Esc` stop, `Ctrl+O` open file

**Command line**

```bash
python Jarvis/read_aloud.py --text "Hello, this is read out loud."
python Jarvis/read_aloud.py --file notes.txt --no-gui --rate 190 --voice 1
cat article.txt | python Jarvis/read_aloud.py            # reads piped input
python Jarvis/read_aloud.py --file notes.txt --save notes.wav
python Jarvis/read_aloud.py --list-voices
```

Options: `--text`, `--file`, `--stdin`, `--save PATH`, `--voice`, `--list-voices`,
`--rate`, `--volume`, `--gui`, `--no-gui`, `--verbose`.

The window needs `tkinter` (bundled with Python on Windows and macOS; on Debian or
Ubuntu install it with `sudo apt install python3-tk`). Without it, the app falls
back to command line mode automatically.

## 📌Read Aloud on your phone (installable web app)

`docs/` holds a mobile version of the Read Aloud app. It is a Progressive Web App:
it installs to the phone's home screen, runs full screen without a browser bar,
and works offline. Speech comes from the text-to-speech engine already on the
device (Google TTS on Android, Siri voices on iOS), so there is nothing to
download and no API key.

**Publish it (one time, about a minute)**

1. Merge this branch into `main`.
2. Repository → **Settings** → **Pages**.
3. Source: **Deploy from a branch** → branch `main`, folder `/docs` → **Save**.
4. Wait for the green check, then open
   `https://<your-username>.github.io/Jarvis-Desktop-Voice-Assistant/` on your phone.

**Install it on the phone**

- **Android (Chrome):** tap the **Install** button in the app, or menu → *Add to Home screen*.
- **iPhone (Safari):** tap **Share** → *Add to Home Screen*. Safari only offers this in Safari itself, not Chrome for iOS.

**What it does**

- Paste or type text, or load a `.txt`/`.md`/`.csv`/`.log` file
- Play, Pause/Resume, Stop, and tap any sentence to jump to it
- The sentence being spoken is highlighted and auto-scrolled
- Voice picker plus speed, pitch and volume, all remembered between launches
- Keeps the screen awake while reading, and keeps your text after you close the app
- On Android it registers as a share target: select text anywhere, **Share** → **Read Aloud**
- Works with no connection once installed

**Test it locally**

```bash
python -m http.server 8000 --directory docs
# then open http://localhost:8000
```

Service workers and installation need HTTPS or `localhost`; opening `index.html`
as a `file://` path will not work.

## Requirements

Python 3.6+

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

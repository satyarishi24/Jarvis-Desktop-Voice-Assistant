/* Read Aloud - reads text out loud using the voices installed on the device. */
(function () {
  "use strict";

  var synth = window.speechSynthesis;
  var MAX_CHUNK = 200; // short chunks keep stop/pause snappy and dodge engine cut-offs

  var el = {
    text: document.getElementById("text"),
    reader: document.getElementById("reader"),
    status: document.getElementById("status"),
    play: document.getElementById("play"),
    pause: document.getElementById("pause"),
    stop: document.getElementById("stop"),
    openFile: document.getElementById("openFile"),
    fileInput: document.getElementById("fileInput"),
    clear: document.getElementById("clear"),
    settings: document.getElementById("settings"),
    settingsToggle: document.getElementById("settingsToggle"),
    voice: document.getElementById("voice"),
    rate: document.getElementById("rate"),
    pitch: document.getElementById("pitch"),
    volume: document.getElementById("volume"),
    rateOut: document.getElementById("rateOut"),
    pitchOut: document.getElementById("pitchOut"),
    volumeOut: document.getElementById("volumeOut"),
    installBar: document.getElementById("installBar"),
    installText: document.getElementById("installText"),
    install: document.getElementById("install"),
    installDismiss: document.getElementById("installDismiss")
  };

  var state = {
    chunks: [],
    index: 0,
    generation: 0, // invalidates callbacks from utterances we cancelled
    playing: false,
    paused: false,
    voices: [],
    wakeLock: null
  };

  // ---------------------------------------------------------------- helpers
  function setStatus(message) {
    el.status.textContent = message;
  }

  function store(key, value) {
    try { localStorage.setItem("readaloud." + key, value); } catch (e) { /* private mode */ }
  }

  function load(key, fallback) {
    try {
      var value = localStorage.getItem("readaloud." + key);
      return value === null ? fallback : value;
    } catch (e) {
      return fallback;
    }
  }

  /* Splits text into sentence sized chunks, mirroring the desktop app. */
  function chunkText(text) {
    var chunks = [];
    var pieces = String(text || "").split(/(?<=[.!?;:])\s+|\n+/);

    for (var i = 0; i < pieces.length; i++) {
      var piece = pieces[i].trim();
      if (!piece) continue;

      while (piece.length > MAX_CHUNK) {
        var cut = piece.lastIndexOf(" ", MAX_CHUNK);
        if (cut <= 0) cut = MAX_CHUNK;
        chunks.push(piece.slice(0, cut).trim());
        piece = piece.slice(cut).trim();
      }
      if (piece) chunks.push(piece);
    }
    return chunks;
  }

  // ----------------------------------------------------------------- voices
  function populateVoices() {
    state.voices = synth ? synth.getVoices() : [];
    var preferred = load("voice", "");
    el.voice.innerHTML = "";

    if (!state.voices.length) {
      var option = document.createElement("option");
      option.value = "";
      option.textContent = "Device default voice";
      el.voice.appendChild(option);
      return;
    }

    var lang = (navigator.language || "en").toLowerCase();
    var fallbackIndex = 0;

    state.voices.forEach(function (voice, index) {
      var option = document.createElement("option");
      option.value = voice.voiceURI;
      option.textContent = voice.name + " (" + voice.lang + ")";
      el.voice.appendChild(option);

      if (voice.voiceURI === preferred) fallbackIndex = index;
      else if (!preferred && voice.default) fallbackIndex = index;
      else if (!preferred && !state.voices[fallbackIndex].default &&
               voice.lang.toLowerCase() === lang) fallbackIndex = index;
    });

    el.voice.selectedIndex = fallbackIndex;
  }

  function selectedVoice() {
    var uri = el.voice.value;
    for (var i = 0; i < state.voices.length; i++) {
      if (state.voices[i].voiceURI === uri) return state.voices[i];
    }
    return null;
  }

  // ------------------------------------------------------------ reading view
  function showReader(show) {
    el.reader.hidden = !show;
    el.text.hidden = show;
  }

  function renderChunks() {
    el.reader.innerHTML = "";
    state.chunks.forEach(function (chunk, index) {
      var span = document.createElement("span");
      span.className = "chunk";
      span.dataset.index = String(index);
      span.textContent = chunk + " ";
      span.addEventListener("click", function () { playFrom(index); });
      el.reader.appendChild(span);
    });
  }

  function markChunk(index) {
    var spans = el.reader.querySelectorAll(".chunk");
    for (var i = 0; i < spans.length; i++) {
      spans[i].classList.toggle("active", i === index);
      spans[i].classList.toggle("done", i < index);
    }
    var active = spans[index];
    if (active && active.scrollIntoView) {
      active.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }

  // -------------------------------------------------------------- wake lock
  function requestWakeLock() {
    if (!navigator.wakeLock || state.wakeLock) return;
    navigator.wakeLock.request("screen").then(function (lock) {
      state.wakeLock = lock;
      lock.addEventListener("release", function () { state.wakeLock = null; });
    }).catch(function () { /* not critical */ });
  }

  function releaseWakeLock() {
    if (state.wakeLock) {
      state.wakeLock.release().catch(function () {});
      state.wakeLock = null;
    }
  }

  // --------------------------------------------------------------- playback
  function updateButtons() {
    el.play.textContent = state.paused ? "Resume" : "Play";
    el.play.disabled = state.playing && !state.paused;
    el.pause.disabled = !state.playing || state.paused;
    el.stop.disabled = !state.playing && !state.paused;
  }

  function speakChunk(index) {
    if (index >= state.chunks.length) {
      finish(true);
      return;
    }

    state.index = index;
    markChunk(index);

    var utterance = new SpeechSynthesisUtterance(state.chunks[index]);
    var generation = state.generation;
    var voice = selectedVoice();

    if (voice) {
      utterance.voice = voice;
      utterance.lang = voice.lang;
    }
    utterance.rate = parseFloat(el.rate.value);
    utterance.pitch = parseFloat(el.pitch.value);
    utterance.volume = parseFloat(el.volume.value);

    utterance.onend = function () {
      if (generation !== state.generation) return; // cancelled, ignore
      speakChunk(index + 1);
    };

    utterance.onerror = function (event) {
      if (generation !== state.generation) return;
      if (event.error === "interrupted" || event.error === "canceled") return;
      setStatus("Speech error: " + event.error + ". Try another voice.");
      finish(false);
    };

    setStatus("Reading sentence " + (index + 1) + " of " + state.chunks.length + ".");
    synth.speak(utterance);
  }

  function playFrom(index) {
    if (!synth) {
      setStatus("This browser has no speech engine. Try Chrome or Safari.");
      return;
    }

    state.generation++;
    synth.cancel();
    state.playing = true;
    state.paused = false;
    requestWakeLock();
    updateButtons();
    speakChunk(index);
  }

  function start() {
    if (state.paused) { // resume replays the sentence that was interrupted
      playFrom(state.index);
      return;
    }

    var text = el.text.value.trim();
    if (!text) {
      setStatus("There is nothing to read yet.");
      return;
    }

    state.chunks = chunkText(text);
    if (!state.chunks.length) {
      setStatus("There is nothing to read yet.");
      return;
    }

    store("text", el.text.value);
    renderChunks();
    showReader(true);
    playFrom(0);
  }

  function pause() {
    if (!state.playing) return;
    // Cancel rather than synth.pause(): pause/resume is unreliable on iOS,
    // so playback restarts at the current sentence instead.
    state.generation++;
    synth.cancel();
    state.playing = false;
    state.paused = true;
    releaseWakeLock();
    updateButtons();
    setStatus("Paused at sentence " + (state.index + 1) + ".");
  }

  function finish(completed) {
    state.generation++;
    state.playing = false;
    state.paused = false;
    releaseWakeLock();
    updateButtons();
    if (completed) {
      markChunk(state.chunks.length); // clears the highlight
      setStatus("Finished reading.");
    }
  }

  function stop() {
    synth.cancel();
    finish(false);
    showReader(false);
    setStatus("Stopped.");
  }

  // ----------------------------------------------------------------- wiring
  el.play.addEventListener("click", start);
  el.pause.addEventListener("click", pause);
  el.stop.addEventListener("click", stop);

  el.clear.addEventListener("click", function () {
    stop();
    el.text.value = "";
    store("text", "");
    setStatus("Cleared.");
  });

  el.openFile.addEventListener("click", function () { el.fileInput.click(); });

  el.fileInput.addEventListener("change", function () {
    var file = el.fileInput.files && el.fileInput.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function () {
      stop();
      el.text.value = String(reader.result || "");
      store("text", el.text.value);
      setStatus("Loaded " + file.name + ".");
    };
    reader.onerror = function () { setStatus("Could not read that file."); };
    reader.readAsText(file);
    el.fileInput.value = "";
  });

  el.settingsToggle.addEventListener("click", function () {
    var open = el.settings.hidden;
    el.settings.hidden = !open;
    el.settingsToggle.setAttribute("aria-expanded", String(open));
  });

  el.reader.addEventListener("dblclick", function () {
    if (!state.playing) showReader(false);
  });

  el.text.addEventListener("input", function () { store("text", el.text.value); });

  function bindSlider(input, output, key, format) {
    input.addEventListener("input", function () {
      output.textContent = format(input.value);
      store(key, input.value);
    });
    input.value = load(key, input.value);
    output.textContent = format(input.value);
  }

  bindSlider(el.rate, el.rateOut, "rate", function (v) { return parseFloat(v).toFixed(1) + "x"; });
  bindSlider(el.pitch, el.pitchOut, "pitch", function (v) { return parseFloat(v).toFixed(1); });
  bindSlider(el.volume, el.volumeOut, "volume", function (v) { return Math.round(v * 100) + "%"; });

  el.voice.addEventListener("change", function () { store("voice", el.voice.value); });

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible" && state.playing) requestWakeLock();
  });

  window.addEventListener("beforeunload", function () { if (synth) synth.cancel(); });

  // ------------------------------------------------------- install prompt
  var deferredPrompt = null;

  window.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();
    deferredPrompt = event;
    if (load("installDismissed", "") !== "1") {
      el.installBar.hidden = false;
      el.install.hidden = false;
      el.installText.textContent = "Install Read Aloud on your phone.";
    }
  });

  el.install.addEventListener("click", function () {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(function () {
      deferredPrompt = null;
      el.installBar.hidden = true;
    });
  });

  el.installDismiss.addEventListener("click", function () {
    store("installDismissed", "1");
    el.installBar.hidden = true;
  });

  function isStandalone() {
    return window.matchMedia("(display-mode: standalone)").matches ||
           window.navigator.standalone === true;
  }

  function isIOS() {
    return /iP(hone|ad|od)/.test(navigator.platform || "") ||
           (/Mac/.test(navigator.platform || "") && navigator.maxTouchPoints > 1);
  }

  if (isIOS() && !isStandalone() && load("installDismissed", "") !== "1") {
    el.installBar.hidden = false;
    el.installText.textContent = "To install: tap Share, then Add to Home Screen.";
  }

  // --------------------------------------------------- startup / share text
  function initialText() {
    var params = new URLSearchParams(location.search);
    var shared = [params.get("title"), params.get("text"), params.get("url")]
      .filter(Boolean).join("\n\n");
    if (shared) {
      history.replaceState(null, "", location.pathname);
      return shared;
    }
    return load("text", "");
  }

  el.text.value = initialText();

  if (!synth) {
    setStatus("This browser has no speech engine. Try Chrome or Safari.");
    el.play.disabled = true;
  } else {
    populateVoices();
    if (typeof synth.onvoiceschanged !== "undefined") {
      synth.onvoiceschanged = populateVoices;
    }
    updateButtons();
  }

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("sw.js").catch(function () { /* offline only */ });
    });
  }

  window.ReadAloud = { chunkText: chunkText, state: state }; // exposed for tests
})();

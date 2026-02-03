<p align="center">
  <img src="assets/altenglish-logo.svg" width="160" alt="AltEnglish Logo">
</p>
# AltEnglish

AltEnglish is an experimental, engineered writing system for English that encodes **speech sounds (phonemes)** into a **feature-based script**, instead of relying on historically irregular spelling.

This repository provides a Python CLI tool that:

1. Accepts an English word written in today’s standard alphabet
2. Looks up its pronunciation using CMUdict (ARPAbet phonemes)
3. Converts the pronunciation into **AltEnglish symbols**
4. Generates two audio outputs:
   - **traditional.wav** – standard English pronunciation
   - **new.wav** – phoneme-driven pronunciation (i.e. reading the AltEnglish script)

---

## Why AltEnglish?

Modern English spelling preserves historical and morphological information but performs poorly as a phonetic system.  
AltEnglish explores a **sound-first alternative** by designing a script where:

- One sound maps to one symbol
- Similar sounds have visually related symbols
- Pronunciation is directly readable from the script
- Errors are easier to detect

This project is both a **linguistic experiment** and a **practical transliteration tool**.

---

## Features

- 🔤 Transliteration from standard English → AltEnglish symbols
- 🧠 Pronunciation lookup using CMUdict (via `pronouncing`)
- 🔊 Dual audio output:
  - Orthography-based speech
  - Phoneme-based speech
- 🧩 Extensible, engineered phoneme-to-symbol mapping
- 🧪 Designed for experimentation and further research

---

## How It Works (High Level)

**Input**
```

language

```

**CMUdict pronunciation**
```

L AE1 NG G W IH0 JH

```

**AltEnglish symbols**
```

⊣> ▼ ⌂° ⌂· □> ▲| Ω+·

````

**Audio output**
- `traditional.wav` → “language”
- `new.wav` → phoneme-accurate spoken form

---

## Requirements

### Python
- Python **3.9+** recommended

### System Dependency (for audio output)

AltEnglish uses **espeak-ng** (or `espeak`) to generate WAV files.

#### Install espeak-ng

**Ubuntu / Debian**
```bash
sudo apt-get update
sudo apt-get install -y espeak-ng
````

**macOS (Homebrew)**

```bash
brew install espeak-ng
```

**Windows**

* Install `espeak-ng`
* Ensure `espeak-ng.exe` is available in your system PATH

> If `espeak-ng` is not installed, AltEnglish will still output symbols but skip audio generation.

---

## Installation

```bash
git clone https://github.com/<your-username>/AltEnglish.git
cd AltEnglish

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

---

## Project Structure

```
AltEnglish/
├── src/
│   └── altenglish.py
├── requirements.txt
└── README.md
```

---

## Usage

Run the tool:

```bash
python src/altenglish.py
```

Example session:

```text
Enter an English word: this

CMUdict phones: DH IH1 S
Engineered symbols: ∆~· ▲| ⊣~
Done.
Generated:
  - traditional.wav
  - new.wav
```

---

## Roadmap

* [ ] Sentence and paragraph support
* [ ] Dialect modes (General American, RP, Indian English)
* [ ] G2P fallback for out-of-vocabulary words
* [ ] Custom glyph font for AltEnglish symbols
* [ ] Web demo with live audio playback

---

## License

Choose one and add a LICENSE file:

* GPL-3.0

````

---

import re
import shutil
import subprocess
import argparse
from typing import List, Optional, Tuple
from pathlib import Path

import pronouncing

# Output directory for generated audio
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


# -----------------------------
# 1) Engineered symbol mapping
# -----------------------------
# We keep exactly the engineered system style you chose:
# Base shapes encode place; modifiers encode manner; dot encodes voicing.

# Consonants from our design (plus a small necessary extension for English: /f/ and /v/)
# We add a "labiodental base" symbol: "⌁" (engineered placeholder glyph).
#   - /f/ = ⌁~
#   - /v/ = ⌁~·
ENGINEERED = {
    # Bilabial (□)
    "P": "□",
    "B": "□·",
    "M": "□°",
    "W": "□>",

    # Alveolar (⊣)
    "T": "⊣",
    "D": "⊣·",
    "S": "⊣~",
    "Z": "⊣~·",
    "N": "⊣°",
    "L": "⊣>",
    "R": "⊣>>",

    # Velar (⌂)
    "K": "⌂",
    "G": "⌂·",
    "NG": "⌂°",

    # Dental (∆)
    "TH": "∆~",     # /θ/
    "DH": "∆~·",    # /ð/

    # Postalveolar / Palatal-ish (Ω)
    "SH": "Ω~",     # /ʃ/
    "ZH": "Ω~·",    # /ʒ/
    "CH": "Ω+",     # /tʃ/
    "JH": "Ω+·",    # /dʒ/

    # Glottal (○)
    "HH": "○~",     # /h/

    # Labiodental extension (needed for real English coverage)
    "F": "⌁~",      # engineered base for labiodental
    "V": "⌁~·",
}

# Vowels from our design (approximate mapping from CMUdict vowel phonemes)
# Reminder of our engineered vowel keys:
# ▲  /i/   (see)
# ▲| /ɪ/   (sit)
# ▶  /e/   (say)
# ▶| /ɛ/   (bed)
# ▼  /æ/   (cat)
# ▼| /ʌ/   (cup)
# ▶— /o/   (go)
# ▲— /u/   (food)
# ▼— /ɑ/   (father)
# ▶|| /ə/  (schwa)

# Diphthongs: we render as two vowel symbols in sequence (compact + transparent).
VOWELS = {
    "IY": "▲",        # see
    "IH": "▲|",       # sit
    "EY": "▶",        # say (approx)
    "EH": "▶|",       # bed
    "AE": "▼",        # cat
    "AH": "▼|",       # cup (approx)
    "AX": "▶||",      # schwa
    "OW": "▶—",       # go (approx)
    "UW": "▲—",       # food
    "AA": "▼—",       # father
    # Common CMUdict vowels not explicitly listed in our earlier minimal set:
    # We'll map them to nearest engineered vowel for usability.
    "AO": "▼—",       # law/caught -> map near /ɑ/ (accent-dependent)
    "UH": "▲—",       # book -> not perfect; closest in our minimal set
    "ER": "▶||⊣>>",   # r-colored schwa-ish: schwa + r-approximant
    # Diphthongs:
    "AY": "▼▲",       # price: /aɪ/ -> low-front-ish + high-front
    "AW": "▼▲—",      # mouth: /aʊ/ -> low + high-back
    "OY": "▶—▲|",     # choice: /ɔɪ/ -> back-mid-ish + near /ɪ/
}


# ---------------------------------------
# 2) Phoneme utilities (CMUdict handling)
# ---------------------------------------
_STRESS_DIGITS = re.compile(r"[012]$")

def strip_stress(arpabet_phone: str) -> str:
    """Remove stress digits from CMUdict phones, e.g., AH0 -> AH"""
    return _STRESS_DIGITS.sub("", arpabet_phone)

def word_to_arpabet(word: str) -> Optional[List[str]]:
    """
    Return a list of ARPAbet phones for the word using CMUdict via pronouncing.
    Picks the first pronunciation if multiple exist.
    """
    w = word.lower().strip()
    phones = pronouncing.phones_for_word(w)
    if not phones:
        return None
    # phones like: 'HH AH0 L OW1'
    return phones[0].split()

def arpabet_to_engineered_symbols(phones: List[str]) -> Tuple[str, List[str]]:
    """
    Convert ARPAbet phones to engineered symbols.
    Returns:
      - a space-separated engineered symbol string
      - a list of phones that couldn't be mapped (if any)
    """
    out = []
    missing = []

    for ph in phones:
        base = strip_stress(ph)

        if base in ENGINEERED:
            out.append(ENGINEERED[base])
        elif base in VOWELS:
            out.append(VOWELS[base])
        else:
            missing.append(base)
            out.append(f"<?>({base})")  # visible marker

    return " ".join(out), missing


def tokenize_words(text: str) -> List[str]:
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text)


def tokenize_with_punctuation(text: str) -> List[str]:
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|\\s+|[^A-Za-z\\s]", text)


# ---------------------------------------
# 3) Audio generation (espeak-ng)
# ---------------------------------------
# We generate:
#  - traditional.wav by speaking the original word
#  - new.wav by speaking a phoneme string (eSpeak phoneme notation)
#
# Note: eSpeak's phoneme notation is *not* IPA. It's its own set.
# We'll map ARPAbet -> approximate eSpeak phonemes.
ESPEAK_PH = {
    # consonants
    "P": "p", "B": "b", "M": "m", "W": "w",
    "T": "t", "D": "d", "S": "s", "Z": "z", "N": "n", "L": "l", "R": "r",
    "K": "k", "G": "g", "NG": "N",
    "TH": "T", "DH": "D",
    "SH": "S", "ZH": "Z",
    "CH": "tS", "JH": "dZ",
    "HH": "h",
    "F": "f", "V": "v",

    # vowels (approx)
    "IY": "i:",   # see
    "IH": "I",    # sit
    "EY": "eI",   # say
    "EH": "E",    # bed
    "AE": "a",    # cat (approx)
    "AH": "V",    # cup (approx)
    "AX": "@",    # schwa
    "OW": "oU",   # go
    "UW": "u:",   # food
    "AA": "A:",   # father
    "AO": "O:",   # law/caught
    "UH": "U",    # book
    "ER": "3:",   # r-colored
    "AY": "aI",
    "AW": "aU",
    "OY": "OI",
}

def espeak_available() -> bool:
    return shutil.which("espeak-ng") is not None or shutil.which("espeak") is not None

def get_espeak_cmd() -> str:
    # prefer espeak-ng if present
    return shutil.which("espeak-ng") or shutil.which("espeak") or "espeak-ng"

def arpabet_to_espeak_phonemes(phones: List[str]) -> Tuple[str, List[str]]:
    """
    Convert ARPAbet phones into eSpeak phoneme string inside [[...]].
    Returns:
      - phoneme string (e.g., '[[h@loU]]' or '[[h @ l oU]]')
      - list of phones not mapped
    """
    parts = []
    missing = []
    for ph in phones:
        base = strip_stress(ph)
        if base in ESPEAK_PH:
            parts.append(ESPEAK_PH[base])
        else:
            missing.append(base)
    # Spaces can help eSpeak parse, so keep them
    return "[[" + " ".join(parts) + "]]", missing


def arpabet_to_espeak_parts(phones: List[str]) -> Tuple[List[str], List[str]]:
    parts = []
    missing = []
    for ph in phones:
        base = strip_stress(ph)
        if base in ESPEAK_PH:
            parts.append(ESPEAK_PH[base])
        else:
            missing.append(base)
    return parts, missing

def make_audio_files(text: str, phones_groups: List[List[str]], pause_between_words: bool = False) -> None:
    """
    Create:
      - output/traditional.wav
      - output/new.wav (speaks phoneme string)
    """
    if not espeak_available():
        print("\n[Audio] espeak-ng/espeak not found on PATH.")
        print("        Install espeak-ng to generate WAV files.")
        return

    cmd = get_espeak_cmd()

    traditional_path = OUTPUT_DIR / "traditional.wav"
    new_path = OUTPUT_DIR / "new.wav"

    # 1) Traditional pronunciation
    subprocess.run(
        [cmd, "-v", "en", "-w", str(traditional_path), text],
        check=False
    )

    # 2) New pronunciation via phoneme string
    parts = []
    missing = []
    for group in phones_groups:
        if pause_between_words and parts:
            parts.append(",")
        group_parts, group_missing = arpabet_to_espeak_parts(group)
        if group_parts:
            parts.extend(group_parts)
        missing.extend(group_missing)
    if not parts:
        print("\n[Audio] Warning: no phonemes available for new.wav.")
        return

    phon_str = "[[" + " ".join(parts) + "]]"
    if missing:
        print("\n[Audio] Warning: some phones missing for eSpeak phoneme mode:", missing)
        print("        The 'new.wav' may be approximate.")

    subprocess.run(
        [cmd, "-v", "en", "-w", str(new_path), phon_str],
        check=False
    )



# ---------------------------------------
# 4) Main
# ---------------------------------------
def main():
    parser = argparse.ArgumentParser(description="AltEnglish transliteration tool")
    parser.add_argument(
        "-m",
        "--mode",
        choices=["word", "sentence"],
        default="word",
        help="Process a single word or a full sentence",
    )
    parser.add_argument(
        "--preserve-punctuation",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Preserve punctuation in sentence output",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Skip WAV generation",
    )
    parser.add_argument("text", nargs="*", help="Input word or sentence")
    args = parser.parse_args()

    if args.text:
        raw_text = " ".join(args.text).strip()
    else:
        prompt = "Enter an English word: " if args.mode == "word" else "Enter an English sentence: "
        raw_text = input(prompt).strip()

    if not raw_text:
        print("No input.")
        return

    words = tokenize_words(raw_text)
    if not words:
        print("No valid words found in input.")
        return

    if args.mode == "word":
        word = words[0]
        if len(words) > 1:
            print("Warning: multiple words detected. Using the first word only.")

        phones = word_to_arpabet(word)
        if phones is None:
            print(f"Could not find '{word}' in CMUdict.")
            print("Tip: try a different spelling, or add a G2P fallback (see note at end).")
            return

        engineered, missing = arpabet_to_engineered_symbols(phones)

        print("\nCMUdict phones:", " ".join(phones))
        print("Engineered symbols:", engineered)
        if missing:
            print("Unmapped phones (need adding):", missing)

        if not args.no_audio:
            make_audio_files(word, [phones])

    else:
        word_entries = []
        missing_words = []
        any_unmapped = []

        for word in words:
            phones = word_to_arpabet(word)
            if phones is None:
                word_entries.append((word, None, None, []))
                missing_words.append(word)
                continue

            engineered, missing = arpabet_to_engineered_symbols(phones)
            word_entries.append((word, phones, engineered, missing))
            if missing:
                any_unmapped.extend(missing)

        print("\nCMUdict phones (by word):")
        for word, phones, _, _ in word_entries:
            if phones is None:
                print(f"  {word}: <not found>")
            else:
                print(f"  {word}: {' '.join(phones)}")

        print("\nEngineered symbols (by word):")
        for word, phones, engineered, _ in word_entries:
            if phones is None:
                print(f"  {word}: <?>({word})")
            else:
                print(f"  {word}: {engineered}")

        tokens = tokenize_with_punctuation(raw_text)
        sentence_symbols = []
        word_symbols_map = {word: engineered for word, phones, engineered, _ in word_entries if phones}
        word_pattern = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
        for token in tokens:
            if word_pattern.fullmatch(token):
                sentence_symbols.append(word_symbols_map.get(token, f"<?>({token})"))
            elif token.isspace():
                sentence_symbols.append(token)
            else:
                if args.preserve_punctuation:
                    sentence_symbols.append(token)
                else:
                    sentence_symbols.append(" ")

        print("\nEngineered symbols (sentence):")
        print("".join(sentence_symbols).strip())

        if missing_words:
            print("\nWords not found in CMUdict:", missing_words)
            print("Tip: try different spelling, or add a G2P fallback (see note at end).")

        if any_unmapped:
            print("Unmapped phones (need adding):", any_unmapped)

        phones_groups = [phones for _, phones, _, _ in word_entries if phones]
        if not args.no_audio:
            make_audio_files(raw_text, phones_groups, pause_between_words=True)

    print("\nDone.")
    if args.no_audio:
        print("\nAudio generation skipped (--no-audio).")
    else:
        print("\nIf audio succeeded, files were written to:")
        print(f"  - {OUTPUT_DIR / 'traditional.wav'}")
        print(f"  - {OUTPUT_DIR / 'new.wav'}")



if __name__ == "__main__":
    main()

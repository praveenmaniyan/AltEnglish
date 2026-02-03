import re
import shutil
import subprocess
from typing import List, Optional, Tuple

import pronouncing


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

def make_audio_files(word: str, phones: List[str]) -> None:
    """
    Create:
      - traditional.wav
      - new.wav (speaks phoneme string)
    """
    if not espeak_available():
        print("\n[Audio] espeak-ng/espeak not found on PATH.")
        print("        Install espeak-ng to generate WAV files.")
        return

    cmd = get_espeak_cmd()

    # 1) Traditional
    subprocess.run([cmd, "-v", "en", "-w", "traditional.wav", word], check=False)

    # 2) New pronunciation via phoneme string
    phon_str, missing = arpabet_to_espeak_phonemes(phones)
    if missing:
        print("\n[Audio] Warning: some phones missing for eSpeak phoneme mode:", missing)
        print("        The 'new.wav' may be incomplete/approximate.")

    subprocess.run([cmd, "-v", "en", "-w", "new.wav", phon_str], check=False)


# ---------------------------------------
# 4) Main
# ---------------------------------------
def main():
    word = input("Enter an English word: ").strip()
    if not word:
        print("No input.")
        return

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

    make_audio_files(word, phones)

    print("\nDone.")
    print("If audio succeeded, you should have:")
    print("  - traditional.wav")
    print("  - new.wav")


if __name__ == "__main__":
    main()

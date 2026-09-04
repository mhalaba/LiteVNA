# LiteVNA Studio

Aplikacja desktopowa do pełnej obsługi **LiteVNA** na **macOS** (także Linux/Windows), z 30 presetami anten oraz interfejsem PL/EN.

## Szybki start na Macu (od zera)

Komendy uruchamiaj w Terminalu. **Musisz być w katalogu repozytorium** (tam, gdzie leży plik `requirements.txt`).

```bash
# 1) Pobierz kod (branch z aplikacją)
git clone https://github.com/mhalaba/LiteVNA.git
cd LiteVNA
git fetch origin
git checkout cursor/litevna-mac-app-82a0

# 2) Sprawdź, że jesteś we właściwym folderze
ls requirements.txt
# → powinno wypisać: requirements.txt

# 3) Środowisko Python + instalacja
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
pip install -e .

# 4) Uruchomienie
litevna-studio
```

Jeśli `litevna-studio` nadal nie działa, użyj:

```bash
python -m litevna.app
# albo:
./scripts/run.sh
```

### Typowe błędy

| Błąd | Przyczyna | Rozwiązanie |
|------|-----------|-------------|
| `Could not open requirements file` | Jesteś w złym katalogu (np. `aed`) | `cd` do folderu `LiteVNA` i `ls requirements.txt` |
| `command not found: litevna-studio` | Pakiet nie zainstalowany albo venv nieaktywne | `source .venv/bin/activate` → `pip install -e .` |
| `python3: command not found` | Brak Pythona | Zainstaluj z https://www.python.org/downloads/macos/ |

## Features / Funkcje

- USB CDC (protokół binarny NanoVNA V2 / LiteVNA) — wszystkie rejestry:
  - Start / Stop / Center / Span / CW (przez start=stop)
  - Punkty skanu 1–65535, uśrednianie 1–80 (IFBW)
  - Moc LF (MS5351) i HF (MAX2871)
  - Wybór kanału S11 / S21 / oba
  - Tryb danych USB lub skalibrowanych na urządzeniu
  - Odczyt baterii, wersji FW/HW, synchronizacja czasu, zrzut ekranu
- Kalibracja SOLT po stronie hosta (Open / Short / Load / Isolation / Thru)
- Formaty śladów: Log Mag, SWR, Smith, Phase, Delay, Polar, Linear, Real, Imag, R, X
- Markery (do 8), TDR (bandpass / impulse / step), velocity factor, electrical delay
- Eksport S1P / S2P / CSV
- **30 presetów anten** (HF, VHF, UHF, Wi‑Fi, GPS, ADS‑B, pełny zakres LiteVNA…)
- **Język polski i angielski**
- **Tryb demo** bez podłączonego urządzenia

## Wymagania (macOS)

- macOS 12+ (Apple Silicon lub Intel)
- Python 3.10+
- LiteVNA podłączona przez USB (pojawi się jako `/dev/cu.*`)

## Instalacja (gdy masz już sklonowane repo)

```bash
cd LiteVNA          # WAŻNE: katalog z requirements.txt
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Uruchomienie

```bash
source .venv/bin/activate
litevna-studio
# lub
python -m litevna.app
# lub
./scripts/run.sh
```

Opcjonalnie utwórz bundle `.app`:

```bash
./scripts/macos_app.sh
open "dist/LiteVNA Studio.app"
```

## Użycie z LiteVNA

1. Podłącz LiteVNA USB-C/USB.
2. Uruchom LiteVNA Studio → **Odśwież porty** → wybierz port `cu.*` → **Połącz**.
3. (Opcjonalnie) wybierz preset anteny → **Zastosuj preset**.
4. Wykonaj kalibrację SOLT na końcu kabla (Open/Short/Load/…).
5. **Pojedynczy** lub **Ciągły** skan, obserwuj SWR / Smith.
6. Eksportuj wynik do S1P/S2P/CSV.

Bez sprzętu włącz **Tryb demo**.

## Testy

```bash
pytest -q
```

## Struktura

```
src/litevna/
  protocol.py      # protokół binarny
  device.py        # USB + demo
  calibration.py   # SOLT
  analysis.py      # SWR, Smith, TDR…
  presets.py       # 30 presetów
  export.py
  i18n/en.json, pl.json
  ui/              # PySide6
```

## Licencja

MIT

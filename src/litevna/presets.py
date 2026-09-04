"""30 built-in antenna / band sweep presets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AntennaPreset:
    id: str
    name_en: str
    name_pl: str
    start_hz: int
    stop_hz: int
    points: int = 201
    average: int = 2
    description_en: str = ""
    description_pl: str = ""
    category: str = "general"

    def localized_name(self, lang: str) -> str:
        return self.name_pl if lang.startswith("pl") else self.name_en

    def localized_description(self, lang: str) -> str:
        return self.description_pl if lang.startswith("pl") else self.description_en


PRESETS: list[AntennaPreset] = [
    AntennaPreset(
        "hf_dipole_80m",
        "HF Dipole 80 m",
        "Dipol HF 80 m",
        3_500_000,
        3_800_000,
        description_en="80 m amateur band dipole check",
        description_pl="Sprawdzenie dipola pasma 80 m",
        category="hf",
    ),
    AntennaPreset(
        "hf_dipole_40m",
        "HF Dipole 40 m",
        "Dipol HF 40 m",
        7_000_000,
        7_200_000,
        description_en="40 m amateur band dipole",
        description_pl="Dipol pasma amatorskiego 40 m",
        category="hf",
    ),
    AntennaPreset(
        "hf_dipole_20m",
        "HF Dipole 20 m",
        "Dipol HF 20 m",
        14_000_000,
        14_350_000,
        description_en="20 m amateur band dipole",
        description_pl="Dipol pasma amatorskiego 20 m",
        category="hf",
    ),
    AntennaPreset(
        "hf_dipole_15m",
        "HF Dipole 15 m",
        "Dipol HF 15 m",
        21_000_000,
        21_450_000,
        description_en="15 m amateur band dipole",
        description_pl="Dipol pasma amatorskiego 15 m",
        category="hf",
    ),
    AntennaPreset(
        "hf_dipole_10m",
        "HF Dipole 10 m",
        "Dipol HF 10 m",
        28_000_000,
        29_700_000,
        description_en="10 m amateur band dipole",
        description_pl="Dipol pasma amatorskiego 10 m",
        category="hf",
    ),
    AntennaPreset(
        "vertical_40m",
        "Vertical 40 m",
        "Pionowa 40 m",
        6_900_000,
        7_300_000,
        description_en="40 m vertical / ground plane",
        description_pl="Antena pionowa / ground plane 40 m",
        category="hf",
    ),
    AntennaPreset(
        "vertical_20m",
        "Vertical 20 m",
        "Pionowa 20 m",
        13_900_000,
        14_450_000,
        description_en="20 m vertical / ground plane",
        description_pl="Antena pionowa / ground plane 20 m",
        category="hf",
    ),
    AntennaPreset(
        "endfed_40_10",
        "End-Fed 40–10 m",
        "End-Fed 40–10 m",
        7_000_000,
        29_700_000,
        points=401,
        description_en="Multi-band end-fed half-wave",
        description_pl="Wielopasmowa end-fed half-wave",
        category="hf",
    ),
    AntennaPreset(
        "g5rv",
        "G5RV / ZS6BKW",
        "G5RV / ZS6BKW",
        3_500_000,
        30_000_000,
        points=401,
        description_en="Classic wire multiband antenna",
        description_pl="Klasyczna wielopasmowa antena drutowa",
        category="hf",
    ),
    AntennaPreset(
        "magnetic_loop_hf",
        "Magnetic Loop HF",
        "Pętla magnetyczna HF",
        5_000_000,
        15_000_000,
        points=301,
        average=4,
        description_en="High-Q magnetic loop resonance search",
        description_pl="Wyszukiwanie rezonansu pętli magnetycznej (wysokie Q)",
        category="hf",
    ),
    AntennaPreset(
        "cobweb",
        "Cobweb Multiband",
        "Cobweb wielopasmowa",
        14_000_000,
        29_700_000,
        points=301,
        description_en="Cobweb / hexagonal multiband",
        description_pl="Cobweb / antena heksagonalna",
        category="hf",
    ),
    AntennaPreset(
        "full_hf",
        "Full HF Scan 1.8–30 MHz",
        "Pełny skan HF 1.8–30 MHz",
        1_800_000,
        30_000_000,
        points=501,
        description_en="Wide HF antenna survey",
        description_pl="Szeroki przegląd anten HF",
        category="hf",
    ),
    AntennaPreset(
        "cb_27mhz",
        "CB 27 MHz",
        "CB 27 MHz",
        26_500_000,
        27_500_000,
        description_en="Citizen Band antenna tune",
        description_pl="Strojenie anteny CB",
        category="vhf",
    ),
    AntennaPreset(
        "yagi_2m",
        "Yagi 2 m",
        "Yagi 2 m",
        144_000_000,
        146_000_000,
        description_en="2 m amateur Yagi / beam",
        description_pl="Yagi / kierunkowa pasma 2 m",
        category="vhf",
    ),
    AntennaPreset(
        "quad_2m",
        "Quad 2 m",
        "Quad 2 m",
        144_000_000,
        146_000_000,
        description_en="2 m cubical quad",
        description_pl="Quad sześcienny 2 m",
        category="vhf",
    ),
    AntennaPreset(
        "yagi_70cm",
        "Yagi 70 cm",
        "Yagi 70 cm",
        430_000_000,
        440_000_000,
        description_en="70 cm amateur Yagi",
        description_pl="Yagi pasma 70 cm",
        category="uhf",
    ),
    AntennaPreset(
        "marine_vhf",
        "Marine VHF",
        "Morski VHF",
        156_000_000,
        162_000_000,
        description_en="Marine VHF antenna",
        description_pl="Antena morskiego VHF",
        category="vhf",
    ),
    AntennaPreset(
        "pmr446",
        "PMR446",
        "PMR446",
        446_000_000,
        446_200_000,
        points=101,
        description_en="PMR446 handheld antenna",
        description_pl="Antena ręczna PMR446",
        category="uhf",
    ),
    AntennaPreset(
        "ism_433",
        "ISM 433 MHz",
        "ISM 433 MHz",
        430_000_000,
        440_000_000,
        description_en="433 MHz ISM / LoRa EU",
        description_pl="ISM / LoRa EU 433 MHz",
        category="uhf",
    ),
    AntennaPreset(
        "ism_868",
        "ISM 868 MHz",
        "ISM 868 MHz",
        863_000_000,
        870_000_000,
        description_en="868 MHz ISM / LoRa EU",
        description_pl="ISM / LoRa EU 868 MHz",
        category="uhf",
    ),
    AntennaPreset(
        "lora_915",
        "LoRa 915 MHz",
        "LoRa 915 MHz",
        902_000_000,
        928_000_000,
        description_en="915 MHz LoRa / ISM US",
        description_pl="LoRa / ISM US 915 MHz",
        category="uhf",
    ),
    AntennaPreset(
        "adsb_1090",
        "ADS-B 1090 MHz",
        "ADS-B 1090 MHz",
        1_080_000_000,
        1_100_000_000,
        description_en="ADS-B receive antenna",
        description_pl="Antena odbiorcza ADS-B",
        category="uhf",
    ),
    AntennaPreset(
        "gps_l1",
        "GPS L1 1575 MHz",
        "GPS L1 1575 MHz",
        1_565_000_000,
        1_585_000_000,
        average=4,
        description_en="GPS/GNSS L1 antenna match",
        description_pl="Dopasowanie anteny GPS/GNSS L1",
        category="microwave",
    ),
    AntennaPreset(
        "wifi_24",
        "Wi-Fi 2.4 GHz",
        "Wi-Fi 2.4 GHz",
        2_400_000_000,
        2_500_000_000,
        description_en="2.4 GHz Wi-Fi / Bluetooth antenna",
        description_pl="Antena Wi-Fi / Bluetooth 2.4 GHz",
        category="microwave",
    ),
    AntennaPreset(
        "wifi_5",
        "Wi-Fi 5 GHz",
        "Wi-Fi 5 GHz",
        5_150_000_000,
        5_850_000_000,
        points=301,
        description_en="5 GHz Wi-Fi antenna",
        description_pl="Antena Wi-Fi 5 GHz",
        category="microwave",
    ),
    AntennaPreset(
        "nfc_1356",
        "NFC / RFID 13.56 MHz",
        "NFC / RFID 13.56 MHz",
        13_000_000,
        14_000_000,
        points=101,
        average=4,
        description_en="13.56 MHz NFC/HF RFID coil",
        description_pl="Cewka NFC/HF RFID 13.56 MHz",
        category="hf",
    ),
    AntennaPreset(
        "discone_wide",
        "Discone Wideband",
        "Discone szerokopasmowa",
        25_000_000,
        1_300_000_000,
        points=501,
        description_en="Wideband discone survey",
        description_pl="Przegląd szerokopasmowej discone",
        category="wideband",
    ),
    AntennaPreset(
        "full_vhf",
        "Full VHF 30–300 MHz",
        "Pełny VHF 30–300 MHz",
        30_000_000,
        300_000_000,
        points=401,
        description_en="VHF antenna survey",
        description_pl="Przegląd anten VHF",
        category="vhf",
    ),
    AntennaPreset(
        "full_uhf",
        "Full UHF 300–3000 MHz",
        "Pełny UHF 300–3000 MHz",
        300_000_000,
        3_000_000_000,
        points=501,
        description_en="UHF antenna survey",
        description_pl="Przegląd anten UHF",
        category="uhf",
    ),
    AntennaPreset(
        "litevna_full",
        "LiteVNA Full Range 50 kHz–6.3 GHz",
        "Pełny zakres LiteVNA 50 kHz–6.3 GHz",
        50_000,
        6_300_000_000,
        points=1001,
        average=1,
        description_en="Maximum LiteVNA frequency span",
        description_pl="Maksymalny zakres częstotliwości LiteVNA",
        category="wideband",
    ),
]


assert len(PRESETS) == 30, f"Expected 30 presets, got {len(PRESETS)}"


def get_preset(preset_id: str) -> AntennaPreset | None:
    for p in PRESETS:
        if p.id == preset_id:
            return p
    return None


def presets_by_category() -> dict[str, list[AntennaPreset]]:
    out: dict[str, list[AntennaPreset]] = {}
    for p in PRESETS:
        out.setdefault(p.category, []).append(p)
    return out

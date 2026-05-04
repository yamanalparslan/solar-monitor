"""
Ortak yardimci fonksiyonlar.
"""

from math import isclose


def parse_id_list(id_string):
    """
    ID listesini parse eder. Virgül ve tire destegi.

    Ornekler:
        "1,2,3" -> [1, 2, 3]
        "1-5" -> [1, 2, 3, 4, 5]
        "1,3-5,7" -> [1, 3, 4, 5, 7]

    Args:
        id_string (str): Parse edilecek ID string'i

    Returns:
        tuple: (parsed_ids: list, errors: list)
            - parsed_ids: Basariyla parse edilen ID'ler
            - errors: Parse edilemeyen kisimlar
    """
    ids = set()
    errors = []

    if not id_string or not id_string.strip():
        return [], ["Bos ID listesi"]

    parts = id_string.split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            try:
                range_parts = part.split("-")
                if len(range_parts) != 2:
                    errors.append(f"Gecersiz aralik formati: '{part}'")
                    continue

                start, end = map(int, range_parts)

                if start > end:
                    errors.append(f"Gecersiz aralik (baslangic > bitis): '{part}'")
                    continue

                if start < 1 or end > 255:
                    errors.append(f"ID aralik disi (1-255): '{part}'")
                    continue

                for i in range(start, end + 1):
                    ids.add(i)

            except ValueError:
                errors.append(f"Gecersiz sayi formati: '{part}'")
        else:
            try:
                id_val = int(part)
                if id_val < 1 or id_val > 255:
                    errors.append(f"ID aralik disi (1-255): '{part}'")
                    continue
                ids.add(id_val)
            except ValueError:
                errors.append(f"Gecersiz sayi: '{part}'")

    return sorted(list(ids)), errors


def format_id_list_display(ids):
    """
    ID listesini kullanici dostu formatta gosterir.
    """
    if not ids:
        return "Hic ID yok"

    if len(ids) <= 5:
        return f"[{', '.join(map(str, ids))}]"

    first_few = ", ".join(map(str, ids[:3]))
    return f"[{first_few}, ... toplam {len(ids)} ID]"


def to_signed16(value):
    """
    Unsigned 16-bit Modbus register'ini signed integer'a cevirir.
    """
    value = int(value)
    return value - 65536 if value > 32767 else value


def decode_temperature_register(raw_value, configured_scale, min_c=-40.0, max_c=120.0):
    """
    Ham sicaklik register degerini mantikli Celsius araligina cevirir.

    Bazi cihazlar sicakligi signed olarak, bazilari ise 0.1 / 0.01 / 0.001
    carpaniyla doner. Kayitli carpanda hata olsa bile makul aralikta bir
    sonuc yakalanirsa onu tercih ederiz.
    """
    if raw_value is None:
        return 0.0

    signed_raw = to_signed16(raw_value)
    scale_candidates = [configured_scale, 0.1, 0.01, 0.001]
    used_scales = []

    for scale in scale_candidates:
        if any(isclose(scale, seen, rel_tol=0.0, abs_tol=1e-12) for seen in used_scales):
            continue
        used_scales.append(scale)

        candidate = signed_raw * float(scale)
        if min_c <= candidate <= max_c:
            return candidate

    return signed_raw * float(configured_scale)


def normalize_temperature_value(value, min_c=-40.0, max_c=120.0):
    """
    Veritabanina yanlis olcekle yazilmis sicakliklari gosterim icin normalize eder.
    """
    if value is None:
        return 0.0

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return 0.0

    for divisor in (1, 10, 100, 1000):
        candidate = numeric_value / divisor
        if min_c <= candidate <= max_c:
            return candidate

    return numeric_value

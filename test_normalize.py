def normalize_hata_kodu(kod, fault_map):
    normalized = 0
    seen = {}
    for bit in range(32):
        if (kod >> bit) & 1:
            desc = fault_map.get(bit, "")
            if desc and desc != "Spare":
                if desc not in seen:
                    # Find the first bit that has this description in the fault_map
                    # to keep it consistent
                    first_bit = bit
                    for b, d in fault_map.items():
                        if d == desc:
                            first_bit = b
                            break
                    seen[desc] = first_bit
                normalized |= (1 << seen[desc])
    return normalized

fault_map = {
    0: "Error A",
    1: "Error A",
    2: "Error B"
}

print(f"kod=1 (bit 0): {normalize_hata_kodu(1, fault_map)}")
print(f"kod=2 (bit 1): {normalize_hata_kodu(2, fault_map)}")
print(f"kod=3 (bit 0,1): {normalize_hata_kodu(3, fault_map)}")
print(f"kod=7 (bit 0,1,2): {normalize_hata_kodu(7, fault_map)}")

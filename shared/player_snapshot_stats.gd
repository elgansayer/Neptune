extends RefCounted

## Preserve the four legacy stat nibbles. Range 16 uses spare flag bit 10,
## rather than overflowing into the adjacent bomb-capacity nibble.
const RANGE_HIGH_BIT := 1 << 10

static func pack(max_bombs: int, bomb_range: int, bombs_placed: int,
		skate_count: int, bomb_type: int, flags: int) -> Array:
	var s1 := (max_bombs << 12) | ((bomb_range & 15) << 8) | (bombs_placed << 4) | skate_count
	var s2 := (bomb_type << 16) | (flags & ~RANGE_HIGH_BIT) | ((bomb_range & 16) << 6)
	return [s1, s2]

static func unpack(packed: Array) -> Dictionary:
	var s1: int = packed[0] if packed.size() > 0 else 0x1200
	var s2: int = packed[1] if packed.size() > 1 else 0
	return {
		"max_bombs": (s1 >> 12) & 15,
		"bomb_range": ((s1 >> 8) & 15) | ((s2 >> 6) & 16),
		"bombs_placed": (s1 >> 4) & 15,
		"skate_count": s1 & 15,
		"bomb_type": (s2 >> 16) & 255,
		"flags": s2 & 0xFFFF,
	}

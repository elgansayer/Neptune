extends RefCounted

## Presentation only: fit authoritative geometry without changing tile/physics size.
static func fit(map_pixels: Vector2, viewport_size: Vector2, top_inset: float, bottom_inset: float = 0.0) -> Dictionary:
	if not map_pixels.is_finite() or not viewport_size.is_finite() or not is_finite(top_inset) or not is_finite(bottom_inset) or map_pixels.x <= 0 or map_pixels.y <= 0 or viewport_size.x <= 0 or viewport_size.y <= top_inset + bottom_inset or top_inset < 0 or bottom_inset < 0:
		return {"accepted": false}
	var margin := 4.0
	var available := viewport_size - Vector2(margin * 2, top_inset + bottom_inset + margin * 2)
	if available.x <= 0 or available.y <= 0: return {"accepted": false}
	# Preserve native pixels on larger displays; shrink uniformly only when needed.
	var zoom := minf(1.0, minf(available.x / map_pixels.x, available.y / map_pixels.y))
	return {"accepted": true, "zoom": Vector2.ONE * zoom,
		"position": map_pixels * 0.5 - Vector2(0, (top_inset - bottom_inset) * 0.5 / zoom)}

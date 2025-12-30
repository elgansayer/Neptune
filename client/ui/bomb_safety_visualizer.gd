extends Node2D
class_name BombSafetyVisualizer

## Visualizes which tiles are safe/unsafe for bomb planting
## Shows bot's perspective: Green = safe to plant, Red = death trap, Yellow = marginal

const RenderingLayers = preload("res://shared/rendering_layers.gd")

var tile_size: float = 16.0
var map_width: int = 0
var map_height: int = 0
var safety_data: Dictionary = {}  # tile_key -> safety_status (0=death, 1=marginal, 2=safe)
var enabled: bool = true

func _ready() -> void:
	z_index = RenderingLayers.DEBUG_OVERLAY  # High-level debug overlay
	print("[BombSafetyVisualizer] Initialized")

func set_map_size(width: int, height: int) -> void:
	map_width = width
	map_height = height
	print("[BombSafetyVisualizer] Map size set to %dx%d" % [width, height])
	queue_redraw()

func update_tile_size(new_size: float) -> void:
	tile_size = new_size
	queue_redraw()

func update_safety_data(new_data: Dictionary) -> void:
	"""
	Receives safety evaluation from server AI:
	{
		"tile_key": {
			"status": 0 (death trap) | 1 (marginal - tight timing) | 2 (safe with escape),
			"escape_tile": Vector2i or null,
			"explored_tiles": int,
			"soft_blocks": int,
			"margin_ms": float
		}
	}
	"""
	safety_data = new_data
	if not new_data.is_empty():
		print("[BombSafetyVisualizer] Received %d tile evaluations" % new_data.size())
		# Count statuses
		var status_counts = {0: 0, 1: 0, 2: 0}
		for tile_key in new_data:
			var tile_data = new_data[tile_key]
			var status = tile_data.get("status", -1)
			if status in status_counts:
				status_counts[status] += 1
		print("[BombSafetyVisualizer] Status breakdown: status 0 (rejected)=%d, status 1 (marginal)=%d, status 2 (safe)=%d" % [status_counts[0], status_counts[1], status_counts[2]])
		# Debug: Print first tile's data
		var first_key = new_data.keys()[0]
		var first_data = new_data[first_key]
		print("[BombSafetyVisualizer] Sample tile %s: %s" % [first_key, str(first_data)])
	queue_redraw()

func _draw() -> void:
	if not visible or not enabled or map_width == 0 or map_height == 0:
		return
	
	if safety_data.is_empty():
		print("[BombSafetyVisualizer] _draw called but no safety_data")
		return
	
	print("[BombSafetyVisualizer] Drawing %d tiles" % safety_data.size())
	
	# Draw semi-transparent overlay for each evaluated tile
	for tile_key in safety_data:
		var data = safety_data[tile_key]
		var coords = tile_key.split(",")
		if coords.size() != 2:
			continue
		
		var tile_x = int(coords[0])
		var tile_y = int(coords[1])
		
		# Skip out-of-bounds
		if tile_x < 0 or tile_x >= map_width or tile_y < 0 or tile_y >= map_height:
			continue
		
		var pixel_x = tile_x * tile_size
		var pixel_y = tile_y * tile_size
		var rect = Rect2(pixel_x, pixel_y, tile_size, tile_size)
		
		# Draw status-based colored overlay
		var status = data.get("status", 0)
		var color: Color
		match status:
			0: color = Color(0.6, 0.0, 0.0, 0.75)  # Dark red - unsafe (high contrast)
			1: color = Color(0.0, 0.35, 0.9, 0.6)  # Blue - marginal
			2: color = Color(0.0, 0.35, 0.0, 0.8)  # Dark green - safe (unchanged)
			_: color = Color(1.0, 1.0, 1.0, 0.2)  # White fallback
		
		draw_rect(rect, color, true)
		
		# Draw text labels with small font in corners
		var font_size = 8  # Small fixed size to fit in corners
		
		# TOP-LEFT: Block count (white number only)
		if "soft_blocks" in data:
			var blocks = data["soft_blocks"]
			var text = str(blocks)
			var text_pos = rect.position + Vector2(1, font_size)
			# Black outline
			draw_string(ThemeDB.fallback_font, text_pos + Vector2(-1, -1), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.BLACK)
			draw_string(ThemeDB.fallback_font, text_pos + Vector2(1, -1), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.BLACK)
			draw_string(ThemeDB.fallback_font, text_pos + Vector2(-1, 1), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.BLACK)
			draw_string(ThemeDB.fallback_font, text_pos + Vector2(1, 1), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.BLACK)
			# White text
			draw_string(ThemeDB.fallback_font, text_pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.WHITE)
		
		# BOTTOM-RIGHT: Actual score (yellow) - show "0" for rejected tiles
		var score_text = ""
		if "final_score" in data:
			score_text = "%.0f" % data["final_score"]
		elif data.get("status", 0) == 0:
			score_text = "0"  # Rejected tiles get score of 0
		
		if score_text != "":
			var text_size = ThemeDB.fallback_font.get_string_size(score_text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size)
			var text_pos = rect.position + Vector2(tile_size - text_size.x - 1, tile_size - 1)
			# Draw black outline for contrast
			draw_string(ThemeDB.fallback_font, text_pos + Vector2(-1, -1), score_text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.BLACK)
			draw_string(ThemeDB.fallback_font, text_pos + Vector2(1, -1), score_text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.BLACK)
			draw_string(ThemeDB.fallback_font, text_pos + Vector2(-1, 1), score_text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.BLACK)
			draw_string(ThemeDB.fallback_font, text_pos + Vector2(1, 1), score_text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.BLACK)
			# Draw yellow text on top
			draw_string(ThemeDB.fallback_font, text_pos, score_text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.YELLOW)
		
		# Draw arrow to escape tile if present (both marginal and safe)
		if data.has("escape_tile"):
			var escape = data.get("escape_tile")
			# Handle both Vector2i and Dictionary {x, y} formats from server
			var escape_pos: Vector2i
			if escape is Vector2i:
				escape_pos = escape
			elif escape is Dictionary and escape.has("x") and escape.has("y"):
				escape_pos = Vector2i(int(escape.x), int(escape.y))
			else:
				continue  # Skip invalid escape data
			
			var escape_center = Vector2(escape_pos.x * tile_size + tile_size/2, escape_pos.y * tile_size + tile_size/2)
			var plant_center = Vector2(pixel_x + tile_size/2, pixel_y + tile_size/2)
			
			# Color arrow based on status: dark green for safe, blue for marginal
			var arrow_color = Color(0.0, 0.35, 0.0, 1.0) if data.get("status") == 2 else Color(0.0, 0.35, 0.9, 1.0)
			draw_line(plant_center, escape_center, arrow_color, 1.5)
			
			# Arrow head
			var dir = (escape_center - plant_center).normalized()
			var arrow_tip = escape_center
			var arrow_left = arrow_tip - dir * 4 + Vector2(-dir.y, dir.x) * 3
			var arrow_right = arrow_tip - dir * 4 + Vector2(dir.y, -dir.x) * 3
			draw_line(arrow_tip, arrow_left, arrow_color, 1.5)
			draw_line(arrow_tip, arrow_right, arrow_color, 1.5)

func toggle_enabled() -> void:
	enabled = !enabled
	queue_redraw()
	print("[BombSafetyVisualizer] Toggled: ", enabled)

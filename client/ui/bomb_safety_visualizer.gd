extends Node2D
class_name BombSafetyVisualizer

## Visualizes which tiles are safe/unsafe for bomb planting
## Shows bot's perspective: Green = safe to plant, Red = death trap, Yellow = marginal

var tile_size: float = 16.0
var map_width: int = 0
var map_height: int = 0
var safety_data: Dictionary = {}  # tile_key -> safety_status (0=death, 1=marginal, 2=safe)
var enabled: bool = true

func _ready() -> void:
	z_index = 5  # Above threat matrix but below players
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
	queue_redraw()

func _draw() -> void:
	if not enabled or map_width == 0 or map_height == 0:
		return
	
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
		
		# Color based on safety status (distinct from threat matrix)
		var color: Color
		match data.get("status", 0):
			0:  # Unsafe - no escape
				color = Color(0.60, 0.20, 0.80, 0.45)  # Purple
			1:  # Marginal - tight timing
				color = Color(1.00, 0.55, 0.00, 0.40)  # Orange
			2:  # Safe - escape route exists
				color = Color(0.00, 0.80, 1.00, 0.35)  # Cyan
			_:
				color = Color(0.5, 0.5, 0.5, 0.3)  # Gray for unknown
		
		draw_rect(rect, color)
		
		# Draw small indicator for soft blocks count
		var blocks = data.get("soft_blocks", 0)
		if blocks > 0:
			var text_pos = Vector2(pixel_x + 2, pixel_y + tile_size - 2)
			draw_string(ThemeDB.fallback_font, text_pos, str(blocks), HORIZONTAL_ALIGNMENT_LEFT, -1, 8, Color.WHITE)
		
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
			
			# Color arrow based on status: cyan for safe, orange for marginal
			var arrow_color = Color.CYAN if data.get("status") == 2 else Color.ORANGE
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

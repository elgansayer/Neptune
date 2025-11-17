extends Node2D
class_name ThreatMatrixVisualizer

## Debug visualization for AI threat matrix
## Shows ALL tiles color-coded by safety level

@export var enabled: bool = true  ## Toggle visualization on/off (starts enabled for testing)
@export var opacity: float = 0.6  ## Overlay opacity

var threat_matrix: Dictionary = {}
var current_time_msec: float = 0.0
var tile_size: float = GameConfig.TILE_SIZE
var map_width: int = 0
var map_height: int = 0

# Simple color scheme: Green = safe, Red = dangerous
const COLOR_SAFE = Color(0.0, 1.0, 0.0, 0.3)           # Green - completely safe
const COLOR_DISTANT = Color(0.5, 1.0, 0.0, 0.4)        # Yellow-green - far future threat (>2.5s)
const COLOR_WARNING = Color(1.0, 1.0, 0.0, 0.5)        # Yellow - warning (1.5-2.5s)
const COLOR_DANGER = Color(1.0, 0.5, 0.0, 0.6)         # Orange - dangerous (0.5-1.5s)
const COLOR_IMMEDIATE = Color(1.0, 0.0, 0.0, 0.7)      # Red - immediate danger (<0.5s)

func _ready():
	z_index = 100  # Draw on top of most things but below UI
	print("[ThreatMatrixVisualizer] Initialized, enabled: ", enabled)
	queue_redraw()

func set_map_size(width: int, height: int) -> void:
	map_width = width
	map_height = height
	print("[ThreatMatrixVisualizer] Map size set to ", width, "x", height)
	queue_redraw()

func update_threat_matrix(matrix: Dictionary, time_msec: float) -> void:
	threat_matrix = matrix
	current_time_msec = time_msec
	
	if enabled:
		queue_redraw()

func toggle_visualization() -> void:
	enabled = !enabled
	queue_redraw()
	print("[ThreatMatrix] Visualization ", "enabled" if enabled else "disabled")

func _draw():
	if not enabled:
		return
	
	if map_width == 0 or map_height == 0:
		# Map size not set yet
		return
	
	# Draw ALL tiles with color-coded safety
	for y in range(map_height):
		for x in range(map_width):
			var tile_key = "%d,%d" % [x, y]
			var color: Color
			
			if threat_matrix.has(tile_key):
				var explosion_time: float = threat_matrix[tile_key]
				var time_until_explosion: float = explosion_time - current_time_msec
				color = _get_threat_color(time_until_explosion)
			else:
				# No threat - safe
				color = COLOR_SAFE
			
			# Draw filled rectangle for this tile
			var rect_pos = Vector2(x * tile_size, y * tile_size)
			var rect_size = Vector2(tile_size, tile_size)
			color.a *= opacity
			draw_rect(Rect2(rect_pos, rect_size), color)
	
	# Draw legend in top-left
	var legend_x = 10.0
	var legend_y = 10.0
	var legend_size = 12.0
	
	draw_rect(Rect2(legend_x, legend_y, legend_size, legend_size), COLOR_SAFE)
	draw_string(ThemeDB.fallback_font, Vector2(legend_x + legend_size + 5, legend_y + 10), "SAFE", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color.WHITE)
	
	legend_y += 15
	draw_rect(Rect2(legend_x, legend_y, legend_size, legend_size), COLOR_DANGER)
	draw_string(ThemeDB.fallback_font, Vector2(legend_x + legend_size + 5, legend_y + 10), "DANGER", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color.WHITE)
	
	legend_y += 15
	draw_rect(Rect2(legend_x, legend_y, legend_size, legend_size), COLOR_IMMEDIATE)
	draw_string(ThemeDB.fallback_font, Vector2(legend_x + legend_size + 5, legend_y + 10), "CRITICAL", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color.WHITE)

func _get_threat_color(time_until_explosion_ms: float) -> Color:
	if time_until_explosion_ms < 500.0:
		return COLOR_IMMEDIATE
	elif time_until_explosion_ms < 1500.0:
		return COLOR_DANGER
	elif time_until_explosion_ms < 2500.0:
		return COLOR_WARNING
	elif time_until_explosion_ms < 4000.0:
		return COLOR_DISTANT
	else:
		return COLOR_SAFE

func _input(event: InputEvent) -> void:
	# Toggle with F3 key
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_F3:
			toggle_visualization()

func _process(_delta: float) -> void:
	# Continuously redraw when enabled (for time countdown updates)
	if enabled:
		queue_redraw()

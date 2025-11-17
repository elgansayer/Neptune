extends Node2D
class_name ThreatMatrixVisualizer

## Debug visualization for AI threat matrix
## Shows ALL tiles color-coded by safety level + grid info + timing

@export var enabled: bool = true  ## Toggle visualization on/off (starts enabled for testing)
@export var opacity: float = 0.7  ## Overlay opacity
@export var show_grid_coords: bool = true  ## Show x,y coordinates on tiles
@export var show_timing: bool = true  ## Show milliseconds until explosion

var threat_matrix: Dictionary = {}
var current_time_msec: float = 0.0
var tile_size: float = 64.0  # Will be updated when map loads
var map_width: int = 0
var map_height: int = 0

# Color scheme with better contrast
const COLOR_SAFE = Color(0.0, 0.8, 0.0, 0.4)           # Green - completely safe
const COLOR_DISTANT = Color(0.4, 1.0, 0.0, 0.5)        # Yellow-green - far future (>2.5s)
const COLOR_WARNING = Color(1.0, 1.0, 0.0, 0.6)        # Yellow - warning (1.5-2.5s)
const COLOR_DANGER = Color(1.0, 0.6, 0.0, 0.7)         # Orange - dangerous (0.5-1.5s)
const COLOR_IMMEDIATE = Color(1.0, 0.0, 0.0, 0.8)      # Red - immediate (<0.5s)

func _ready():
	z_index = 100  # Draw on top of most things but below UI
	position = Vector2.ZERO  # Ensure we start at origin
	print("[ThreatMatrixVisualizer] Initialized at position: ", position)
	print("[ThreatMatrixVisualizer] Enabled: ", enabled)
	print("[ThreatMatrixVisualizer] Global position: ", global_position)
	queue_redraw()

func set_map_size(width: int, height: int) -> void:
	map_width = width
	map_height = height
	tile_size = GameConfig.TILE_SIZE  # Update tile size from GameConfig after map is loaded
	print("[ThreatMatrixVisualizer] Map size set to ", width, "x", height)
	print("[ThreatMatrixVisualizer] Tile size updated to: ", tile_size, "px")
	queue_redraw()

func update_threat_matrix(matrix: Dictionary, time_msec: float) -> void:
	threat_matrix = matrix
	current_time_msec = time_msec
	
	# Debug: Print first few threat entries with exact coordinates
	if threat_matrix.size() > 0 and threat_matrix.size() < 50:
		print("[ThreatMatrix] Updated with %d tiles at time %.0f:" % [threat_matrix.size(), time_msec])
		print("[ThreatMatrix] Drawing from position: ", position, " global: ", global_position)
		print("[ThreatMatrix] Tile size: ", tile_size)
		var count = 0
		for key in threat_matrix.keys():
			if count < 5:  # Only print first 5
				var explosion_time = threat_matrix[key]
				var time_until = explosion_time - time_msec
				var coords = key.split(",")
				var tile_x = int(coords[0])
				var tile_y = int(coords[1])
				var pixel_x = tile_x * tile_size
				var pixel_y = tile_y * tile_size
				print("  - Tile %s: grid(%d,%d) → pixels(%.0f,%.0f) explodes in %.0fms" % [key, tile_x, tile_y, pixel_x, pixel_y, time_until])
				count += 1
	
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
		return
	
	var font = ThemeDB.fallback_font
	var font_size = 8
	
	# DEBUG: Draw map boundary to verify positioning
	var map_rect = Rect2(0, 0, map_width * tile_size, map_height * tile_size)
	draw_rect(map_rect, Color.MAGENTA, false, 3.0)  # Magenta border around entire map
	
	# Draw ALL tiles with color-coded safety
	for y in range(map_height):
		for x in range(map_width):
			var tile_key = "%d,%d" % [x, y]
			var color: Color
			var time_until_explosion: float = -1.0
			
			if threat_matrix.has(tile_key):
				var explosion_time: float = threat_matrix[tile_key]
				time_until_explosion = explosion_time - current_time_msec
				color = _get_threat_color(time_until_explosion)
			else:
				# No threat - safe
				color = COLOR_SAFE
			
			# Draw filled rectangle for this tile
			var rect_pos = Vector2(x * tile_size, y * tile_size)
			var rect_size = Vector2(tile_size, tile_size)
			color.a *= opacity
			draw_rect(Rect2(rect_pos, rect_size), color)
			
			# Draw grid coordinates
			if show_grid_coords:
				var coord_text = "%d,%d" % [x, y]
				var text_pos = rect_pos + Vector2(4, 12)
				draw_string(font, text_pos, coord_text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.WHITE)
			
			# Draw timing info for threatened tiles
			if show_timing and time_until_explosion >= 0:
				var ms_text = "%.0fms" % time_until_explosion
				var text_pos = rect_pos + Vector2(4, tile_size - 8)
				draw_string(font, text_pos, ms_text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.WHITE)
	
	# Draw comprehensive legend
	_draw_legend()

func _draw_legend() -> void:
	var font = ThemeDB.fallback_font
	var viewport_width = get_viewport_rect().size.x
	var legend_x = viewport_width - 220.0  # Top-right corner
	var legend_y = 10.0  # Top of screen
	var legend_size = 12.0
	var line_height = 16.0
	
	# Background for legend
	draw_rect(Rect2(legend_x - 5, legend_y - 5, 215, 125), Color(0, 0, 0, 0.8))
	
	# Title
	draw_string(font, Vector2(legend_x, legend_y), "THREAT MATRIX", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color.YELLOW)
	legend_y += line_height
	
	# Color indicators
	draw_rect(Rect2(legend_x, legend_y, legend_size, legend_size), COLOR_SAFE)
	draw_string(font, Vector2(legend_x + legend_size + 3, legend_y + 10), "SAFE", HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color.WHITE)
	legend_y += line_height
	
	draw_rect(Rect2(legend_x, legend_y, legend_size, legend_size), COLOR_DISTANT)
	draw_string(font, Vector2(legend_x + legend_size + 3, legend_y + 10), "DISTANT >2.5s", HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color.WHITE)
	legend_y += line_height
	
	draw_rect(Rect2(legend_x, legend_y, legend_size, legend_size), COLOR_WARNING)
	draw_string(font, Vector2(legend_x + legend_size + 3, legend_y + 10), "WARNING 1.5-2.5s", HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color.WHITE)
	legend_y += line_height
	
	draw_rect(Rect2(legend_x, legend_y, legend_size, legend_size), COLOR_DANGER)
	draw_string(font, Vector2(legend_x + legend_size + 3, legend_y + 10), "DANGER 0.5-1.5s", HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color.WHITE)
	legend_y += line_height
	
	draw_rect(Rect2(legend_x, legend_y, legend_size, legend_size), COLOR_IMMEDIATE)
	draw_string(font, Vector2(legend_x + legend_size + 3, legend_y + 10), "CRITICAL <0.5s", HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color.WHITE)
	legend_y += line_height + 3
	
	# Info text
	draw_string(font, Vector2(legend_x, legend_y), "F3:Viz F4:Coord F5:Time", HORIZONTAL_ALIGNMENT_LEFT, -1, 8, Color.GRAY)
	legend_y += line_height - 3
	draw_string(font, Vector2(legend_x, legend_y), "Threats: %d tiles" % threat_matrix.size(), HORIZONTAL_ALIGNMENT_LEFT, -1, 8, Color.CYAN)

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
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_F3:
			toggle_visualization()
		elif event.keycode == KEY_F4:
			show_grid_coords = !show_grid_coords
			print("[ThreatMatrix] Grid coordinates ", "enabled" if show_grid_coords else "disabled")
			queue_redraw()
		elif event.keycode == KEY_F5:
			show_timing = !show_timing
			print("[ThreatMatrix] Timing info ", "enabled" if show_timing else "disabled")
			queue_redraw()

func _process(_delta: float) -> void:
	# Continuously redraw when enabled (for time countdown updates)
	if enabled:
		queue_redraw()

extends Node2D
class_name AIDebugVisualizer

## AI Debug Visualization System
## Shows danger zones, target positions, paths, and AI reasoning
## Enable/disable with AI_DEBUG environment variable or debug builds

const Constants = preload("res://shared/constants.gd")

# Visualization settings
var enabled: bool = false
var show_danger_zones: bool = true
var show_paths: bool = true
var show_targets: bool = true
var show_reasoning: bool = true

# References
var danger_mapper
var ai_controller
var ai_player: Node2D

# Visual data
var current_reasoning: String = ""
var current_target: Vector2i = Vector2i(-1, -1)
var current_path: Array = []

# Colors
var COLOR_SAFE = Color(0.0, 1.0, 0.0, 0.2)  # Green transparent
var COLOR_LOW_DANGER = Color(1.0, 1.0, 0.0, 0.3)  # Yellow
var COLOR_MEDIUM_DANGER = Color(1.0, 0.5, 0.0, 0.4)  # Orange
var COLOR_HIGH_DANGER = Color(1.0, 0.0, 0.0, 0.5)  # Red
var COLOR_PATH = Color(0.0, 0.5, 1.0, 0.8)  # Blue
var COLOR_TARGET = Color(1.0, 0.0, 1.0, 1.0)  # Magenta

func _init():
	# Enable in debug builds
	if OS.is_debug_build():
		enabled = true

func setup(danger_ref, controller_ref, player_ref):
	danger_mapper = danger_ref
	ai_controller = controller_ref
	ai_player = player_ref
	z_index = 1000  # Draw on top

func _process(_delta):
	if enabled:
		queue_redraw()

func _draw():
	if not enabled or danger_mapper == null:
		return
	
	var current_time = Time.get_ticks_msec() / 1000.0
	
	# Update danger map
	danger_mapper.update(current_time)
	
	# Draw danger zones
	if show_danger_zones:
		_draw_danger_zones(current_time)
	
	# Draw path
	if show_paths and not current_path.is_empty():
		_draw_path()
	
	# Draw target
	if show_targets and current_target != Vector2i(-1, -1):
		_draw_target()
	
	# Draw AI position marker
	if ai_player != null:
		_draw_ai_marker()
	
	# Draw reasoning text
	if show_reasoning and current_reasoning != "":
		_draw_reasoning_text()

func _draw_danger_zones(current_time: float):
	var danger_zones = danger_mapper.get_all_danger_zones()
	
	for tile_key in danger_zones.keys():
		var zone = danger_zones[tile_key]
		var coords = tile_key.split(",")
		var tile_x = int(coords[0])
		var tile_y = int(coords[1])
		
		var tile_pos = Vector2(
			tile_x * Constants.TILE_SIZE,
			tile_y * Constants.TILE_SIZE
		)
		
		# Choose color based on danger intensity and time until explosion
		var time_until = zone.explosion_time - current_time
		var color = COLOR_SAFE
		
		if time_until < 0.5:
			color = COLOR_HIGH_DANGER
		elif time_until < 1.5:
			color = COLOR_MEDIUM_DANGER
		elif time_until < 2.5:
			color = COLOR_LOW_DANGER
		
		# Adjust alpha based on intensity
		color.a = zone.intensity * 0.5
		
		# Draw filled rectangle for danger zone
		draw_rect(
			Rect2(tile_pos, Vector2(Constants.TILE_SIZE, Constants.TILE_SIZE)),
			color
		)
		
		# Draw timer text
		var timer_text = "%.1f" % time_until
		draw_string(
			ThemeDB.fallback_font,
			tile_pos + Vector2(Constants.TILE_SIZE * 0.5, Constants.TILE_SIZE * 0.5),
			timer_text,
			HORIZONTAL_ALIGNMENT_CENTER,
			-1,
			12,
			Color.WHITE
		)

func _draw_path():
	if current_path.size() < 2:
		return
	
	# Draw line through waypoints
	for i in range(current_path.size() - 1):
		var from_pos = current_path[i]
		var to_pos = current_path[i + 1]
		
		draw_line(from_pos, to_pos, COLOR_PATH, 3.0)
		
		# Draw waypoint circles
		draw_circle(from_pos, 5.0, COLOR_PATH)
	
	# Draw final waypoint
	if not current_path.is_empty():
		draw_circle(current_path[-1], 5.0, COLOR_PATH)

func _draw_target():
	var target_pos = Vector2(
		current_target.x * Constants.TILE_SIZE + Constants.TILE_SIZE * 0.5,
		current_target.y * Constants.TILE_SIZE + Constants.TILE_SIZE * 0.5
	)
	
	# Draw crosshair
	var size = 20.0
	draw_line(target_pos + Vector2(-size, 0), target_pos + Vector2(size, 0), COLOR_TARGET, 3.0)
	draw_line(target_pos + Vector2(0, -size), target_pos + Vector2(0, size), COLOR_TARGET, 3.0)
	
	# Draw circle around target
	draw_arc(target_pos, size, 0, TAU, 32, COLOR_TARGET, 2.0)

func _draw_ai_marker():
	# Draw circle around AI player
	draw_circle(ai_player.position, 35.0, Color(0.0, 1.0, 0.0, 0.3))
	draw_arc(ai_player.position, 35.0, 0, TAU, 32, Color(0.0, 1.0, 0.0, 1.0), 2.0)
	
	# Draw direction arrow if moving
	if ai_player.has_method("get_velocity"):
		var velocity = ai_player.velocity if ai_player.velocity.length() > 0 else Vector2.ZERO
		if velocity.length() > 10:
			var arrow_end = ai_player.position + velocity.normalized() * 40.0
			draw_line(ai_player.position, arrow_end, Color.GREEN, 3.0)
			_draw_arrow_head(ai_player.position, arrow_end, Color.GREEN)

func _draw_arrow_head(from: Vector2, to: Vector2, color: Color):
	var direction = (to - from).normalized()
	var perpendicular = Vector2(-direction.y, direction.x)
	
	var arrow_size = 10.0
	var arrow_point1 = to - direction * arrow_size + perpendicular * arrow_size * 0.5
	var arrow_point2 = to - direction * arrow_size - perpendicular * arrow_size * 0.5
	
	draw_line(to, arrow_point1, color, 3.0)
	draw_line(to, arrow_point2, color, 3.0)

func _draw_reasoning_text():
	if ai_player == null:
		return
	
	# Draw text above AI player
	var text_pos = ai_player.position - Vector2(0, 60)
	
	# Draw background for readability
	var text_size = ThemeDB.fallback_font.get_string_size(current_reasoning, HORIZONTAL_ALIGNMENT_CENTER, -1, 14)
	var bg_rect = Rect2(text_pos - Vector2(text_size.x * 0.5 + 5, text_size.y + 2), text_size + Vector2(10, 4))
	draw_rect(bg_rect, Color(0, 0, 0, 0.7))
	
	# Draw text
	draw_string(
		ThemeDB.fallback_font,
		text_pos,
		current_reasoning,
		HORIZONTAL_ALIGNMENT_CENTER,
		-1,
		14,
		Color.WHITE
	)

## Public API for updating visualization data

func update_reasoning(reasoning: String):
	current_reasoning = reasoning

func update_target(target_tile: Vector2i):
	current_target = target_tile

func update_path(path: Array):
	current_path = path.duplicate()

func toggle_enabled():
	enabled = not enabled
	queue_redraw()

func toggle_danger_zones():
	show_danger_zones = not show_danger_zones

func toggle_paths():
	show_paths = not show_paths

func toggle_targets():
	show_targets = not show_targets

func toggle_reasoning():
	show_reasoning = not show_reasoning

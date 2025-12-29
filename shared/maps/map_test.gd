extends Node2D

# Map System Test & Demo
# Showcases the dynamic map generation and loading system
# Run this scene to test different maps

const Constants = preload("res://shared/constants.gd")

var map_manager: Node
var current_map_data: Dictionary = {}
var current_test_index: int = 0

# Test cases
var test_cases := [
	{"type": "file", "name": "Classic Arena", "path": "res://maps/classic_arena.json"},
	{"type": "file", "name": "Open Battlefield", "path": "res://maps/open_battlefield.json"},
	{"type": "file", "name": "Narrow Passages", "path": "res://maps/narrow_passages.json"},
	{"type": "file", "name": "Cross Roads", "path": "res://maps/cross_roads.json"},
	{"type": "file", "name": "Wide Battle Royale", "path": "res://maps/wide_battle_royale.json"},
	{"type": "generate", "name": "Generated: Classic", "style": MapGenerator.MapStyle.CLASSIC},
	{"type": "generate", "name": "Generated: Arena", "style": MapGenerator.MapStyle.ARENA},
	{"type": "generate", "name": "Generated: Maze", "style": MapGenerator.MapStyle.MAZE},
	{"type": "generate", "name": "Generated: Chaos", "style": MapGenerator.MapStyle.CHAOS},
	{"type": "generate", "name": "Generated: Wide", "style": MapGenerator.MapStyle.WIDE},
	{"type": "generate", "name": "Generated: Symmetric", "style": MapGenerator.MapStyle.SYMMETRIC}
]

@onready var camera = $Camera2D
@onready var ui_label = $UI/Label
@onready var map_container = $MapContainer

func _ready():
	# Initialize map manager
	map_manager = load("res://shared/maps/map_manager.gd").new()
	add_child(map_manager)
	
	# Setup UI
	ui_label.text = "Press SPACE to cycle maps | Current: Loading..."
	
	# Load first map
	load_test_case(0)
	
	print("\n========== MAP SYSTEM DEMO ==========")
	print("Controls:")
	print("  SPACE - Next map")
	print("  R - Reload/Regenerate current map")
	print("  L - List all available maps")
	print("  V - Validate current map")
	print("  E - Export current map")
	print("=====================================\n")

func _input(event):
	if event.is_action_pressed("ui_accept"):  # SPACE
		current_test_index = (current_test_index + 1) % test_cases.size()
		load_test_case(current_test_index)
	
	elif event.is_action_pressed("ui_cancel"):  # ESC
		get_tree().quit()
	
	elif event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_R:  # Reload/Regenerate
				print("\n[Demo] Reloading map...")
				reload_current_map()
			KEY_L:  # List maps
				print("\n[Demo] Available maps:")
				var maps = map_manager.list_all_maps()
				for map_info in maps:
					print("  - ", map_info.name, " (", map_info.size, ", ", 
						  map_info.spawn_count, " spawns)")
			KEY_V:  # Validate
				print("\n[Demo] Validating current map...")
				var validation = map_manager.validate_current_map()
				print("  Valid: ", validation.valid)
				if not validation.errors.is_empty():
					print("  Errors: ", validation.errors)
				if not validation.warnings.is_empty():
					print("  Warnings: ", validation.warnings)
			KEY_E:  # Export
				var export_path = "user://exported_map_%d.json" % Time.get_ticks_msec()
				if map_manager.export_current_map(export_path):
					print("\n[Demo] Exported map to: ", export_path)

func load_test_case(index: int):
	var test = test_cases[index]
	print("\n[Demo] Loading test case: ", test.name)
	
	match test.type:
		"file":
			current_map_data = map_manager.load_map(map_manager.MapSource.FILE, test.path)
		"generate":
			current_map_data = map_manager.generate_procedural_map(test.style)
	
	if current_map_data.is_empty():
		push_error("[Demo] Failed to load map")
		ui_label.text = "ERROR: Failed to load map"
		return
	
	render_map()
	update_ui()

func reload_current_map():
	current_map_data = map_manager.reload_map()
	if not current_map_data.is_empty():
		render_map()
		update_ui()

func render_map():
	# Clear existing map visualization
	for child in map_container.get_children():
		child.queue_free()
	
	var grid = current_map_data.grid
	var height = grid.size()
	var width = grid[0].size() if height > 0 else 0
	
	# Draw background
	var bg = ColorRect.new()
	bg.color = Color(0.15, 0.25, 0.15)
	bg.size = Vector2(width * Constants.TILE_SIZE, height * Constants.TILE_SIZE)
	bg.z_index = -1
	map_container.add_child(bg)
	
	# Draw tiles
	for y in range(height):
		for x in range(width):
			var tile_type = grid[y][x]
			
			if tile_type == 0:  # Empty
				continue
			
			var tile = ColorRect.new()
			tile.size = Vector2(Constants.TILE_SIZE - 2, Constants.TILE_SIZE - 2)
			tile.position = Vector2(x * Constants.TILE_SIZE + 1, y * Constants.TILE_SIZE + 1)
			
			match tile_type:
				1:  # Wall
					tile.color = Color(0.3, 0.3, 0.35)
				2:  # Destructible
					tile.color = Color(0.6, 0.5, 0.4)
				_:
					tile.color = Color(1, 0, 1)  # Unknown type (magenta)
			
			map_container.add_child(tile)
	
	# Draw spawn points
	for i in range(current_map_data.spawn_points.size()):
		var spawn_pos = current_map_data.spawn_points[i]
		
		# Create spawn marker
		var marker = ColorRect.new()
		marker.size = Vector2(Constants.TILE_SIZE * 0.6, Constants.TILE_SIZE * 0.6)
		marker.position = spawn_pos - marker.size / 2
		marker.color = Color(0, 1, 0, 0.7)
		marker.z_index = 10
		map_container.add_child(marker)
		
		# Add label
		var label = Label.new()
		label.text = "P" + str(i + 1)
		label.position = spawn_pos + Vector2(-10, -30)
		label.add_theme_font_size_override("font_size", 16)
		label.add_theme_color_override("font_color", Color(0, 1, 0))
		map_container.add_child(label)
	
	# Center camera on map
	camera.position = Vector2(width * Constants.TILE_SIZE / 2, height * Constants.TILE_SIZE / 2)

func update_ui():
	var test = test_cases[current_test_index]
	var metadata = current_map_data.get("metadata", {})
	
	var info_text = "Map %d/%d: %s\n" % [current_test_index + 1, test_cases.size(), current_map_data.get("name", "Unknown")]
	info_text += "Size: %dx%d | " % [current_map_data.width, current_map_data.height]
	info_text += "Spawns: %d | " % current_map_data.spawn_points.size()
	info_text += "Type: %s\n" % test.type
	
	if not metadata.is_empty():
		info_text += "Difficulty: %s | " % metadata.get("difficulty", "N/A")
		info_text += "Players: %s | " % metadata.get("recommended_players", "N/A")
		info_text += "Theme: %s\n" % metadata.get("theme", "N/A")
	
	info_text += "\nPress SPACE for next map | R to reload | V to validate | E to export | ESC to quit"
	
	ui_label.text = info_text
	
	# Print stats
	print("[Demo] Map Info:")
	print("  Name: ", current_map_data.get("name", "Unknown"))
	print("  Size: ", current_map_data.width, "x", current_map_data.height)
	print("  Spawns: ", current_map_data.spawn_points.size())
	print("  Style: ", current_map_data.get("style", "file-based"))

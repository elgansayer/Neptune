extends Node2D
class_name ExplosionRenderer

## Client-side progressive explosion visual with SBomberman sprites
## Handles directional sprites (middle, h/v ends, h/v middle) with 4 size stages

var explosion_id: String = ""
var explosion_pattern: Array = []  # From server
var start_time: float = 0.0
var current_length := 0
var max_length := 0

const GROWTH_INTERVAL = 0.02  # 50 tiles/second

# Sprite size stages (big -> medium -> small -> smaller)
const SIZE_STAGES = ["big", "medium", "small", "smaller"]
var current_size_stage := 0

# Fire sprite nodes by grid position
var fire_nodes := {}  # Vector2i -> AnimatedSprite2D
var tile_data_map := {}  # Vector2i -> Dictionary (stores tile info for sprite updates)

# Explosion sprite paths (organized by size/direction)
const EXPLOSION_BASE_PATH = "res://res/explosion/sbomberman/"

# Animation type to sprite name mapping
const SPRITE_MAP = {
	"middle": "middle",
	"h_middle": "horizontal",
	"v_middle": "verticle",  # Note: typo from original
	"h_end": "horizontal",
	"v_end": "verticle",
	"left": "left",
	"right": "right",
	"up": "up",
	"down": "down"
}

func _ready():
	pass

func initialize(pattern: Array, start_t: float):
	"""Initialize explosion with pattern from server"""
	explosion_pattern = pattern
	start_time = Time.get_ticks_msec() / 1000.0  # Use current time, not server time
	max_length = 0
	
	# Calculate max length from pattern
	for tile in pattern:
		if tile.has("length"):
			max_length = max(max_length, tile["length"])
	
	# Start expansion
	set_physics_process(true)

func _physics_process(_delta):
	var elapsed = Time.get_ticks_msec() / 1000.0 - start_time
	var target_length = int(elapsed / GROWTH_INTERVAL)
	
	# Expand to current length
	while current_length <= target_length and current_length <= max_length:
		expand_to_length(current_length)
		current_length += 1
	
	# Update size stage based on time
	var size_stage = int(elapsed / 0.15)  # Change size every 0.15s
	if size_stage != current_size_stage and size_stage < SIZE_STAGES.size():
		current_size_stage = size_stage
		update_sprite_sizes()
	
	# Clean up after explosion completes
	if current_length > max_length and elapsed > 0.8:
		queue_free()

func expand_to_length(length: int):
	"""Add fire sprites for all tiles at the given length"""
	for tile_data in explosion_pattern:
		if tile_data.get("length", 0) == length:
			# Convert Dictionary grid_pos to Vector2i
			var grid_pos_dict = tile_data["grid_pos"]
			var grid_pos = Vector2i(grid_pos_dict["x"], grid_pos_dict["y"])
			spawn_fire_sprite(grid_pos, tile_data)

func spawn_fire_sprite(grid_pos: Vector2i, tile_data: Dictionary):
	"""Create a fire sprite at the given position"""
	if fire_nodes.has(grid_pos):
		return  # Already spawned
	
	# Store tile data for this position
	tile_data_map[grid_pos] = tile_data
	
	var sprite = Sprite2D.new()
	sprite.centered = true
	
	# Load appropriate sprite based on direction and current size
	var direction = tile_data.get("direction", "middle")
	var is_end = tile_data.get("is_end", false)
	var sprite_type = get_sprite_type(direction, is_end)
	
	var texture_path = get_sprite_path(sprite_type, SIZE_STAGES[0])
	var texture = load_texture_from_png(texture_path)
	if texture:
		sprite.texture = texture
	
	# Apply flip based on direction
	apply_sprite_flip(sprite, direction, is_end)
	
	# Position sprite
	var pixel_pos = GridHelpers.grid_to_pixel(grid_pos)
	sprite.position = pixel_pos
	
	add_child(sprite)
	fire_nodes[grid_pos] = sprite

func load_texture_from_png(path: String) -> ImageTexture:
	"""Load a PNG file as an ImageTexture at runtime"""
	var image = Image.new()
	var err = image.load(path)
	if err != OK:
		return null
	
	var texture = ImageTexture.create_from_image(image)
	return texture

func get_sprite_type(direction: String, is_end: bool) -> String:
	"""Determine sprite type based on direction and position"""
	if direction == "middle":
		return "middle"
	elif direction in ["left", "right"]:
		if is_end:
			return "h_end"
		else:
			return "h_middle"
	elif direction in ["up", "down"]:
		if is_end:
			return "v_end"
		else:
			return "v_middle"
	return "middle"

func get_sprite_path(sprite_type: String, size_stage: String) -> String:
	"""Get path to sprite file based on type and size"""
	var sprite_name = SPRITE_MAP.get(sprite_type, "middle")
	
	# Map size stage to file suffix (big=01, medium=02, small=03, smaller=04)
	var size_suffix = "01"
	match size_stage:
		"big":
			size_suffix = "01"
		"medium":
			size_suffix = "02"
		"small":
			size_suffix = "03"
		"smaller":
			size_suffix = "04"
	
	return EXPLOSION_BASE_PATH + size_stage + "/" + sprite_name + "-" + size_suffix + ".png"

func apply_sprite_flip(sprite: Sprite2D, direction: String, _is_end: bool):
	"""Apply horizontal/vertical flip based on direction"""
	if direction == "right":
		sprite.flip_h = true
	elif direction == "down":
		sprite.flip_v = true

func update_sprite_sizes():
	"""Update all fire sprites to current size stage"""
	if current_size_stage >= SIZE_STAGES.size():
		return
	
	var size_stage = SIZE_STAGES[current_size_stage]
	
	for grid_pos in fire_nodes:
		var sprite = fire_nodes[grid_pos]
		var tile_data = get_tile_data_for_pos(grid_pos)
		if tile_data.is_empty():
			continue
			
		var direction = tile_data.get("direction", "middle")
		var is_end = tile_data.get("is_end", false)
		var sprite_type = get_sprite_type(direction, is_end)
		
		var texture_path = get_sprite_path(sprite_type, size_stage)
		var texture = load_texture_from_png(texture_path)
		if texture:
			sprite.texture = texture

func get_tile_data_for_pos(grid_pos: Vector2i) -> Dictionary:
	"""Find tile data for a grid position"""
	if tile_data_map.has(grid_pos):
		return tile_data_map[grid_pos]
	return {}

# Need to preload GridHelpers
const GridHelpers = preload("res://shared/game_logic/grid_helpers.gd")

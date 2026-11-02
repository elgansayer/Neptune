extends Node2D
class_name ExplosionRenderer

## Client-side progressive explosion visual with SBomberman sprites
## Handles directional sprites (middle, h/v ends, h/v middle) with 4 size stages

var explosion_id: String = ""
var explosion_pattern: Array = []  # From server
var start_time: float = 0.0
var elapsed_time := 0.0
var current_length := 0
var max_length := 0

const GROWTH_INTERVAL = 0.02  # 50 tiles/second
const SIZE_INTERVAL = 0.15
const MIN_DISPLAY_TIME = 0.8

# Sprite size stages (big -> medium -> small -> smaller)
const SIZE_STAGES = ["big", "medium", "small", "smaller"]
var current_size_stage := 0

# Fire sprite nodes by grid position
var fire_nodes := {}  # Vector2i -> ExplosionSegment

const ExplosionSegmentScene = preload("res://client/ui/explosion_segment.tscn")

func _ready():
	set_physics_process(false)

func initialize(pattern: Array, start_t: float, snapshot_time_sec: float):
	"""Sample the event's age in its publishing snapshot, then use physics delta.
	This does not compensate transport delay or recover the Saturn timebase.
	"""
	explosion_pattern = pattern
	start_time = start_t
	elapsed_time = snapshot_time_sec - start_time
	max_length = 0
	
	# Calculate max length from pattern
	for tile in pattern:
		if tile.has("length"):
			max_length = max(max_length, tile["length"])
	
	# GameView adds this node to the tree first, so immediate segments are ready.
	_sample_age()
	set_physics_process(true)

func _physics_process(delta):
	if is_queued_for_deletion() or not is_finite(delta) or delta < 0:
		return
	elapsed_time += delta
	_sample_age()


static func has_finished_age(age: float, length: int) -> bool:
	# Preserve the previous predicate, including long-pattern expansion lifetime.
	return age > MIN_DISPLAY_TIME and age / GROWTH_INTERVAL >= float(length)


func _sample_age() -> void:
	var target_length = int(minf(elapsed_time / GROWTH_INTERVAL, float(max_length)))
	# A delayed first observation must start in the correct phase, including the
	# final size stage after 0.6 seconds. These are existing Neptune constants.
	var size_stage = int(minf(elapsed_time / SIZE_INTERVAL, float(SIZE_STAGES.size() - 1)))
	if size_stage != current_size_stage:
		current_size_stage = size_stage
		update_sprite_sizes()
	
	# Expand to current length
	while current_length <= target_length and current_length <= max_length:
		expand_to_length(current_length)
		current_length += 1
	
	# Clean up after explosion completes
	if current_length > max_length and has_finished_age(elapsed_time, max_length):
		set_physics_process(false)
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

	var direction = tile_data.get("direction", "middle")
	var is_end = tile_data.get("is_end", false)
	var segment = ExplosionSegmentScene.instantiate()
	segment.position = GridHelpers.grid_to_pixel(grid_pos)
	add_child(segment)

	var stage_index = clamp(current_size_stage, 0, SIZE_STAGES.size() - 1)
	var initial_stage = SIZE_STAGES[stage_index] if SIZE_STAGES.size() > 0 else "big"
	segment.configure(direction, is_end, initial_stage)
	fire_nodes[grid_pos] = segment

func update_sprite_sizes():
	"""Update all fire sprites to current size stage"""
	if current_size_stage >= SIZE_STAGES.size():
		return
	
	var size_stage = SIZE_STAGES[current_size_stage]
	
	for segment in fire_nodes.values():
		segment.update_size_stage(size_stage)

# Need to preload GridHelpers
const GridHelpers = preload("res://shared/game_logic/grid_helpers.gd")

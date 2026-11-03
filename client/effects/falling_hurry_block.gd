extends Node2D
class_name FallingHurryBlock
## Falling pressure block for "Hurry Up" mode
## Authentic SNES Super Bomberman 2 physics:
## - Fixed 256 pixel drop height (relative to 16px tiles, scaled for other sizes)
## - Linear velocity: 12 pixels/frame at 60 FPS (no gravity/acceleration)
## - 22 frame drop duration
## - Snap-to-grid on impact
## - Z-index 100 while falling, 0 when landed

signal block_landed(tile: Vector2i)  # Emitted on impact for screen shake, kill checks

# === SNES-ACCURATE CONSTANTS (for 16px reference tile size) ===
# These are scaled proportionally for other tile sizes
const REFERENCE_DROP_HEIGHT := 256  # 16 tiles * 16 pixels
const REFERENCE_FALL_SPEED := 12    # pixels per frame at 60 FPS
const REFERENCE_TILE_SIZE := 16.0

# Z-Index values
const Z_INDEX_FALLING := 100  # Above everything while falling
const Z_INDEX_LANDED := 15    # Same as other hurry blocks when landed

var target_tile: Vector2i
var target_y: float = 0.0
var is_falling := false
var has_landed := false

# Scaled values (calculated at runtime based on GameConfig.TILE_SIZE)
var drop_height: float
var fall_speed_per_frame: float

# Visual components - BlockVisual is defined in FallingHurryBlock.tscn
@onready var block_visual: Node2D = $BlockVisual
@onready var anim_player: AnimationPlayer = $AnimationPlayer
var block_sprite: CanvasItem
var shadow_ref: Node2D  # Reference to the shadow (to hide on landing)

func _ready():
	# Calculate scaled values based on current tile size
	var scale_factor = GameConfig.TILE_SIZE / REFERENCE_TILE_SIZE
	drop_height = REFERENCE_DROP_HEIGHT * scale_factor
	fall_speed_per_frame = REFERENCE_FALL_SPEED * scale_factor
	
	# z_index is already set in FallingHurryBlock.tscn
	set_physics_process(false)  # Don't start falling until explicitly told

func setup(tile: Vector2i, shadow: Node2D = null):
	"""Initialize the falling block for a target tile"""
	target_tile = tile
	shadow_ref = shadow
	
	# Calculate target Y position (tile center)
	target_y = tile.y * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0
	
	# Position block at start (target - drop_height, i.e., way above screen)
	position = Vector2(
		tile.x * GameConfig.TILE_SIZE + GameConfig.TILE_SIZE / 2.0,
		target_y - drop_height
	)
	
	# Set up the block visual inside the BlockVisual container
	_setup_block_visual()

func _setup_block_visual():
	"""Set up the falling block visual inside the BlockVisual container"""
	# Try to load the hard block scene from the mounted map PCK
	var hard_block_path = "res://Hard-block.tscn"
	if ResourceLoader.exists(hard_block_path):
		var scene = load(hard_block_path)
		if scene:
			block_sprite = scene.instantiate()
			block_visual.add_child(block_sprite)
			# Reset position since we handle that at parent level
			block_sprite.position = Vector2.ZERO
			return
	
	# Fallback: Create a simple colored block
	var fallback = ColorRect.new()
	fallback.size = Vector2(GameConfig.TILE_SIZE, GameConfig.TILE_SIZE)
	fallback.position = -Vector2(GameConfig.TILE_SIZE / 2.0, GameConfig.TILE_SIZE / 2.0)  # Center it
	fallback.color = Color(0.5, 0.5, 0.5, 1.0)  # Gray block
	block_sprite = fallback
	block_visual.add_child(block_sprite)

func start_falling():
	"""Begin the fall animation. Called by game_view after shadow warning completes."""
	is_falling = true
	set_physics_process(true)

func _physics_process(_delta):
	"""SNES-accurate linear velocity movement
	   Move exactly fall_speed_per_frame pixels per physics frame (assuming 60 FPS)
	   No gravity, no acceleration - just constant linear velocity"""
	
	if not is_falling or has_landed:
		return
	
	# Move down by fixed amount (linear velocity, no delta - frame-locked like SNES)
	# Godot physics runs at fixed rate, so this gives consistent timing
	position.y += fall_speed_per_frame
	
	# Check for landing (snap to grid on overshoot)
	if position.y >= target_y:
		_on_impact()

func _on_impact():
	"""Handle block landing - SNES-authentic behavior:
	   1. Snap to exact grid position (correct overshoot)
	   2. Change Z-index to ground level
	   3. Hide shadow
	   4. Emit signal for kill checks and screen shake
	   5. Stop physics processing"""
	
	has_landed = true
	is_falling = false
	
	# Snap to exact grid position (fixes the 256 % 12 overshoot)
	position.y = target_y
	
	# Change Z-index to ground level
	z_index = Z_INDEX_LANDED
	
	# Hide the shadow
	if shadow_ref and is_instance_valid(shadow_ref):
		shadow_ref.hide_shadow()
	
	# Stop physics processing
	set_physics_process(false)
	
	# Emit signal for game to handle (screen shake, kill check, etc.)
	block_landed.emit(target_tile)
	
	# Small visual "thud" effect - brief scale pulse
	_play_impact_effect()

func _play_impact_effect():
	"""Quick scale pulse on landing for visual feedback"""
	if anim_player and anim_player.has_animation("impact"):
		anim_player.play("impact")

func get_target_tile() -> Vector2i:
	return target_tile

func is_block_landed() -> bool:
	return has_landed

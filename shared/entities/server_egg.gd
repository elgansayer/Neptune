extends Area2D
class_name ServerEgg

## Server-side Tirra egg entity
## Uses common collectable sizing and collection logic
## Spawns a Tirra mount when collected by a player

## Ratio of tile size for collision trigger (0.0-1.0)
@export_range(0.1, 1.0) var trigger_size_ratio: float = 1.0

var egg_id: String = ""
var collected: bool = false
var destroyed: bool = false

# Collision shape is defined in ServerEgg.tscn
@onready var collision_shape: CollisionShape2D = $CollisionShape2D

# Egg-specific signals
signal egg_collected(egg)
signal egg_destroyed(egg)

# Scene references
# NOTE: These are loaded from PCK at runtime, not preloaded
var TIRRA_SCENE: PackedScene = null
const TIRRA_PICKUP_AREA = preload("res://shared/entities/TirraPickupArea.tscn")

func _ready():
	# Load Tirra scene from PCK at runtime
	TIRRA_SCENE = load("res://tirra.tscn")
	if not TIRRA_SCENE:
		push_warning("[ServerEgg] Failed to load tirra.tscn from PCK")
	
	# Update collision shape to match current GameConfig values
	_update_collision_shape_size()
	
	# Ensure monitoring is enabled
	monitoring = true
	monitorable = false
	
	# Connect collision signal
	body_entered.connect(_on_body_entered)

func _update_collision_shape_size():
	"""Update collision shape to match current GameConfig values"""
	if collision_shape and collision_shape.shape:
		var trigger_size = GameConfig.TILE_SIZE * trigger_size_ratio
		collision_shape.shape.size = Vector2(trigger_size, trigger_size)

func _on_body_entered(body: Node):
	"""Called when something enters the trigger area"""
	print("[ServerEgg] body_entered: ", body.name, " collected=", collected, " destroyed=", destroyed)
	if collected or destroyed:
		return
	
	if _can_be_collected_by(body):
		print("[ServerEgg] Collecting egg!")
		_collect(body)
	else:
		print("[ServerEgg] Cannot be collected by ", body.name)

func _can_be_collected_by(body: Node) -> bool:
	"""Check if player can collect this egg"""
	# Check if it's a player (has is_mounted property, not method)
	if not "is_mounted" in body:
		print("[ServerEgg] Body ", body.name, " doesn't have is_mounted property")
		return false
	
	# If already mounted, check if Tirra is at max level
	if body.is_mounted and body.mounted_tirra:
		if body.mounted_tirra.has_method("get"):
			var level = body.mounted_tirra.get("current_level")
			if level != null and level >= 2:  # ADULT is max level
				print("[ServerEgg] Player already at max Tirra level")
				return false  # Can't collect if already at max
	
	return true

func _collect(body: Node):
	"""Handle egg collection - spawn or level up Tirra"""
	if collected or destroyed:
		return
	collected = true
	set_deferred("monitoring", false)
	# Schedule on the script's static callable, not this soon-to-be-freed egg.
	# Only weak actor/world references cross the physics-query boundary.
	var finish: Callable = ServerEgg._finish_collection
	finish.call_deferred(weakref(body), weakref(get_parent()), TIRRA_SCENE, global_position)
	egg_collected.emit(self)
	queue_free()

static func _finish_collection(player_ref: WeakRef, world_ref: WeakRef, scene: PackedScene, spawn_position: Vector2) -> void:
	var body = player_ref.get_ref()
	var world = world_ref.get_ref()
	if not is_instance_valid(body) or not is_instance_valid(world) or body.is_queued_for_deletion() \
			or world.is_queued_for_deletion() or body.get_parent() != world or body.is_dead:
		return
	# If player already has a mounted Tirra, level it up instead
	if body.is_mounted and body.mounted_tirra:
		if body.mounted_tirra.has_method("level_up"):
			print("[ServerEgg] Upgrading existing Tirra for player: ", body.username if "username" in body else "unknown")
			body.mounted_tirra.level_up()
			
			# Update player's growth level for state sync
			if body.mounted_tirra.has_method("get"):
				body.tirra_growth_level = body.mounted_tirra.get("current_level")
			return
	
	# Spawn new Tirra
	_spawn_tirra(body, world, scene, spawn_position)

static func _spawn_tirra(player: Node, world: Node, scene: PackedScene, spawn_position: Vector2):
	"""Spawn a new Tirra at the egg's position"""
	print("[ServerEgg] Hatching Tirra for player: ", player.username if "username" in player else "unknown")
	
	if not scene:
		push_warning("[ServerEgg] Failed to load tirra.tscn from PCK - ensure blue-tirra.pck is mounted")
		return
	
	# Instantiate the Tirra
	var tirra = scene.instantiate()
	tirra.name = "Tirra_" + str(randi())
	tirra.position = spawn_position
	
	# Add to groups for detection
	tirra.add_to_group("tirras")
	tirra.add_to_group("mounts")
	
	# Add pickup area using scene
	_add_tirra_pickup_area(tirra)
	
	# Add to game world
	if is_instance_valid(world):
		world.add_child(tirra)
		tirra.global_position = spawn_position
		print("[ServerEgg] Tirra spawned at position: ", tirra.global_position)
		
		# Register with game_instance for network sync
		if world.has_method("register_tirra"):
			world.register_tirra(tirra)
	else:
		push_warning("[ServerEgg] No parent to add Tirra to")
		tirra.queue_free()

static func _add_tirra_pickup_area(tirra: Node2D):
	"""Add pickup area to Tirra using scene instance"""
	if tirra.get_node_or_null("PickupArea"):
		return  # Already has one
	
	var pickup_area = TIRRA_PICKUP_AREA.instantiate()
	
	# Update collision size based on current tile size
	var collision = pickup_area.get_node("CollisionShape2D")
	if collision and collision.shape:
		collision.shape.size = Vector2(GameConfig.TILE_SIZE * 0.8, GameConfig.TILE_SIZE * 0.8)
	
	# Connect signal for remounting
	pickup_area.body_entered.connect(ServerEgg._on_tirra_pickup.bind(tirra))
	
	tirra.add_child(pickup_area)
	
	# Enable monitoring after adding to scene tree (deferred)
	pickup_area.set_deferred("monitoring", true)

static func _on_tirra_pickup(body: Node, tirra: Node2D):
	"""Handle player walking over a dropped Tirra"""
	if not is_instance_valid(tirra):
		return
	
	if not body.is_in_group("players") and not body.name.begins_with("Player"):
		return
	
	print("[ServerEgg] Player ", body.name, " walking over Tirra at ", tirra.position)
	
	if body.has_method("mount_tirra"):
		body.call_deferred("mount_tirra", tirra)
	else:
		push_warning("[ServerEgg] Player doesn't have mount_tirra method")

func destroy():
	"""Called when egg is destroyed by explosion"""
	if collected or destroyed:
		return
	
	destroyed = true
	egg_destroyed.emit(self)

func get_tile_position() -> Vector2i:
	"""Get the tile coordinates of this egg"""
	return Vector2i(
		int(floor(position.x / GameConfig.TILE_SIZE)),
		int(floor(position.y / GameConfig.TILE_SIZE))
	)

func get_state() -> Dictionary:
	return {
		"egg_id": egg_id,
		"position": {"x": position.x, "y": position.y}
	}

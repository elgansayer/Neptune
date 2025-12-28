extends "res://items/item.gd"

## Egg power-up - spawns a Tirra mount creature
## When player walks over the hatched Tirra, they mount it

func picked_up(player):
	# Check if player already has a mounted Tirra at max level
	if player.has_method("is_mounted") and player.is_mounted:
		if player.mounted_tirra and player.mounted_tirra.has_method("get"):
			var level = player.mounted_tirra.get("current_level")
			if level != null and level >= 2:  # ADULT is max level
				# Don't consume the egg if already at max level
				return
	
	super.picked_up(player)

func award_player(player):
	# Check if player is already mounted
	if player.has_method("is_mounted") and player.is_mounted:
		if player.mounted_tirra and player.mounted_tirra.has_method("level_up"):
			print("[Egg] Upgrading existing Tirra for player: ", player.username if "username" in player else "unknown")
			player.mounted_tirra.level_up()
			# Update player's growth level for state sync
			if player.mounted_tirra.has_method("get"):
				player.tirra_growth_level = player.mounted_tirra.get("current_level")
			return

	print("[Egg] Hatching Tirra for player: ", player.username if "username" in player else "unknown")
	
	# Try to load Tirra scene from PCK
	var tirra_scene = load("res://tirra.tscn")
	if not tirra_scene:
		push_warning("[Egg] Failed to load tirra.tscn from PCK - ensure blue-tirra.pck is mounted")
		return
	
	# Instantiate the Tirra
	var tirra = tirra_scene.instantiate()
	tirra.name = "Tirra_" + str(randi())
	
	# Position at egg location
	tirra.global_position = global_position
	
	# Add to groups for detection
	tirra.add_to_group("tirras")
	tirra.add_to_group("mounts")  # Alternative group name
	
	# Add collision for player pickup
	_add_tirra_pickup_area(tirra)
	
	# Add to the game world
	var parent = get_parent()
	if parent:
		parent.add_child(tirra)
		print("[Egg] Tirra spawned at position: ", tirra.global_position)
		
		# Register with game_instance for network sync
		var game_instance = parent
		if game_instance.has_method("register_tirra"):
			game_instance.register_tirra(tirra)
	else:
		push_warning("[Egg] No parent to add Tirra to")
		tirra.queue_free()

func _add_tirra_pickup_area(tirra: Node2D) -> void:
	"""Add an Area2D to the Tirra so players can pick it up by walking over it"""
	# Check if tirra already has a pickup area
	if tirra.get_node_or_null("PickupArea"):
		return
	
	var pickup_area = Area2D.new()
	pickup_area.name = "PickupArea"
	pickup_area.collision_layer = 0  # Don't collide with anything
	pickup_area.collision_mask = 2   # Detect players (layer 2)
	pickup_area.monitoring = false   # Start disabled to avoid physics callback errors
	
	# Create collision shape matching tile size
	var collision = CollisionShape2D.new()
	var shape = RectangleShape2D.new()
	shape.size = Vector2(GameConfig.TILE_SIZE * 0.8, GameConfig.TILE_SIZE * 0.8)
	collision.shape = shape
	pickup_area.add_child(collision)
	
	# Store tirra reference in pickup_area metadata so we can access it in the callback
	pickup_area.set_meta("tirra_ref", tirra)
	
	# Connect signal using a lambda that captures the tirra reference
	# This avoids relying on the egg script which gets destroyed
	pickup_area.body_entered.connect(func(body: Node):
		_handle_tirra_pickup(body, tirra)
	)
	
	tirra.add_child(pickup_area)
	
	# Enable monitoring after adding to scene tree (deferred to avoid physics issues)
	pickup_area.set_deferred("monitoring", true)

func _handle_tirra_pickup(body: Node, tirra: Node2D) -> void:
	"""Static-like handler for Tirra pickup - called when player walks over Tirra"""
	# Validate tirra still exists
	if not is_instance_valid(tirra):
		return
	
	# Check if it's a player
	if not body.is_in_group("players") and not body.name.begins_with("Player"):
		return
	
	print("[Egg] Player ", body.name, " walking over Tirra at ", tirra.position)
	
	# Check if player can mount (has the method and isn't already mounted)
	if body.has_method("mount_tirra"):
		# Defer the mount call to avoid physics callback issues
		body.call_deferred("mount_tirra", tirra)
	else:
		push_warning("[Egg] Player doesn't have mount_tirra method - ServerPlayer needs updating")

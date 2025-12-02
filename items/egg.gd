extends "res://items/item.gd"

## Egg power-up - spawns a Tirra companion

func picked_up(player):
	# Check if player already has max tirra level
	if "current_tirra" in player and player.current_tirra:
		if "current_tirra_level" in player.current_tirra:
			if player.current_tirra.current_tirra_level >= 2:
				return
	
	super.picked_up(player)

func award_player(_player):
	print("award_player egg")
	
	# Find world node
	var world = get_node_or_null("/root/World")
	if not world:
		push_warning("Egg: Could not find World node")
		return
	
	if not world.has_method("get_grid_position"):
		push_warning("Egg: World missing get_grid_position method")
		return
	
	# Get grid position for spawn
	var grid_position = world.get_grid_position(self.position)
	
	# Pick and spawn tirra
	var tirra_path = pick_random_tirra()
	if not ResourceLoader.exists(tirra_path):
		push_warning("Egg: Tirra scene not found: " + tirra_path)
		return
	
	var tirra = load(tirra_path).instantiate()
	if world.has_method("get_center_position_from_grid"):
		tirra.position = world.get_center_position_from_grid(grid_position)
	else:
		tirra.position = self.position
	
	if "group_tirras" in world:
		tirra.add_to_group(world.group_tirras)
	
	world.add_child(tirra)

func pick_random_tirra() -> String:
	var colour = "blue"
	return "res://tirra/" + colour + "_tirra_0.tscn"

extends Node
class_name RenderingLayers

## Godot-native rendering layer system using CanvasLayers and Y-sorting
## Leverages Godot's built-in features for optimal performance

## CanvasLayer indices (for major separation)
## Note: Higher layer = rendered on top, independent of z_index
const CANVAS_BACKGROUND: int = -10   # Background tiles, floor
const CANVAS_GAME: int = 0           # Main gameplay (uses Y-sorting)
const CANVAS_UI: int = 10            # HUD, menus (no Y-sorting)
const CANVAS_DEBUG: int = 100        # Debug overlays

## Z-Index within game canvas (for entity stacking)
## These work WITH Y-sorting - entities at same Y use z_index for order
const FLOOR: int = -100
const SHADOWS: int = -50
const ITEMS: int = 5         # Powerups, eggs - ABOVE floor/map
const BOMBS: int = 10         # Above items
const EXPLOSIONS: int = 15    # Above bombs
const PLAYER_BASE: int = 100       # Player sprite
const PLAYER_EFFECTS: int = 150    # Mounted creatures, flames
const PLAYER_UI: int = 200         # Name tags, health bars

## Debug layers (within debug canvas)
const DEBUG_PATHS: int = 1000
const DEBUG_ARROWS: int = 1001
const DEBUG_OVERLAY: int = 4096

## Node groups for batch z_index management
const GROUP_ITEMS: String = "render_items"
const GROUP_BOMBS: String = "render_bombs"
const GROUP_EXPLOSIONS: String = "render_explosions"
const GROUP_PLAYERS: String = "render_players"
const GROUP_DEBUG: String = "render_debug"

## Apply z_index and add to rendering group
static func setup_node(node: Node2D, layer: int, group: String = "") -> void:
	if not node:
		return
	
	node.z_index = layer
	node.z_as_relative = false  # Absolute z_index
	
	if group and not node.is_in_group(group):
		node.add_to_group(group)
	
	if OS.is_debug_build():
		print("[RenderingLayers] z=%d group=%s node=%s" % [layer, group, node.name])

## Batch update all nodes in a group
static func update_group_layer(tree: SceneTree, group: String, new_layer: int) -> void:
	for node in tree.get_nodes_in_group(group):
		if node is Node2D:
			node.z_index = new_layer

## Setup Y-sorting container (Godot's built-in feature)
static func setup_ysort_container(container: Node2D) -> void:
	container.y_sort_enabled = true
	# Use Godot's sorting optimization
	if container.has_method("set_sort_enabled"):
		container.set_sort_enabled(true)

## Create a CanvasLayer node with proper settings
static func create_canvas_layer(layer_index: int, name: String) -> CanvasLayer:
	var canvas = CanvasLayer.new()
	canvas.name = name
	canvas.layer = layer_index
	canvas.follow_viewport_enabled = false  # Game uses camera
	return canvas

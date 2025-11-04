extends Node2D
# Simple test to verify PCK loading and player instantiation

func _ready():
	print("=== Player PCK Test ===")
	
	# Force re-mount to ensure it's loaded before we check
	var pck_path = "res://characters/player-robin-hood.pck"
	print("[Test] Explicitly mounting PCK: ", pck_path)
	var mount_success = ProjectSettings.load_resource_pack(pck_path)
	print("[Test] Mount result: ", mount_success)
	
	# Wait a frame for the filesystem to update
	await get_tree().process_frame
	
	# Try various possible scene paths
	var possible_paths = [
		"res://player.tscn",
		"res://Player/PlayerRobinHood.tscn",
		"res://player/PlayerRobinHood.tscn",
		"res://PlayerRobinHood.tscn"
	]
	
	print("\n[Test] Searching for player scene...")
	var found_scene = null
	var found_path = ""
	
	for path in possible_paths:
		print("  Trying: ", path)
		if ResourceLoader.exists(path):
			print("    ✓ FOUND!")
			found_path = path
			found_scene = load(path)
			break
		else:
			print("    ✗ Not found")
	
	if found_scene:
		print("\n[Test] ✓ Successfully loaded scene from: ", found_path)
		var player_instance = found_scene.instantiate()
		print("[Test] Root node type: ", player_instance.get_class())
		print("[Test] Root node name: ", player_instance.name)
		print("[Test] Children count: ", player_instance.get_child_count())
		print("[Test] Scene structure:")
		print_node_tree(player_instance, 0)
		player_instance.queue_free()
	else:
		print("\n[Test] ✗ Could not find player scene in any expected location")
		print("[Test] Listing res:// contents...")
		list_directory("res://", 0, 2)
	
	print("\n=== Test Complete ===")
	await get_tree().create_timer(0.5).timeout
	get_tree().quit()

func print_node_tree(node: Node, indent: int):
	var prefix = "  ".repeat(indent)
	print(prefix, "- ", node.name, " (", node.get_class(), ")")
	for child in node.get_children():
		print_node_tree(child, indent + 1)

func list_directory(path: String, depth: int, max_depth: int):
	if depth > max_depth:
		return
	
	var dir = DirAccess.open(path)
	if not dir:
		return
	
	var prefix = "  ".repeat(depth)
	dir.list_dir_begin()
	var file_name = dir.get_next()
	
	while file_name != "":
		var full_path = path + ("" if path.ends_with("/") else "/") + file_name
		if dir.current_is_dir() and not file_name.begins_with("."):
			print(prefix, "[DIR] ", file_name)
			list_directory(full_path, depth + 1, max_depth)
		elif not file_name.begins_with("."):
			print(prefix, "[FILE] ", file_name)
		file_name = dir.get_next()


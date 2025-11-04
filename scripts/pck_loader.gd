extends Node
# PCK Loader - Mounts external resource packs at startup

func _ready():
	# Mount the player PCK file
	var pck_path = "res://characters/player-robin-hood.pck"
	var success = ProjectSettings.load_resource_pack(pck_path)
	
	if success:
		print("[PCKLoader] Successfully mounted: ", pck_path)
	else:
		push_error("[PCKLoader] Failed to mount PCK: ", pck_path)

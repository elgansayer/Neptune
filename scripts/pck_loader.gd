extends Node
# PCK Loader - Mounts external resource packs at startup

func _ready():
	# Mount the player PCK file
	var player_pck = "res://characters/player-robin-hood.pck"
	var player_success = ProjectSettings.load_resource_pack(player_pck)
	
	if player_success:
		print("[PCKLoader] Successfully mounted: ", player_pck)
	else:
		push_error("[PCKLoader] Failed to mount PCK: ", player_pck)
	
	# Mount the Tirra (mount creature) PCK file
	var tirra_pck = "res://tirra/blue-tirra.pck"
	var tirra_success = ProjectSettings.load_resource_pack(tirra_pck)
	
	if tirra_success:
		print("[PCKLoader] Successfully mounted: ", tirra_pck)
	else:
		push_warning("[PCKLoader] Tirra PCK not found (optional): ", tirra_pck)

extends Node

## Deliberately untrusted network client. Uses the real server, no game fixtures.
var transport: ENetMultiplayerPeer
var mode := "future"
var attempted := false

func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--protocol-probe="):
			mode = arg.trim_prefix("--protocol-probe=")
	var api := multiplayer as SceneMultiplayer
	api.auth_callback = func(_id: int, _data: PackedByteArray): pass
	api.peer_authenticating.connect(func(id: int):
		attempted = true
		var data := JSON.stringify({"format": "neptune.protocol/1", "versions": [3]}).to_utf8_buffer()
		match mode:
			"malformed": data = "not JSON".to_utf8_buffer()
			"invalid": data = JSON.stringify({"format": "neptune.protocol/1", "versions": [true]}).to_utf8_buffer()
			"duplicate": data = JSON.stringify({"format": "neptune.protocol/1", "versions": [1, 1]}).to_utf8_buffer()
			"oversized": data = "x".repeat(2048).to_utf8_buffer()
			"bytes": data = PackedByteArray([255, 254])
			"format": data = JSON.stringify({"format": 1, "versions": [1]}).to_utf8_buffer()
			"silent": return
		if api.send_auth(id, data) != OK:
			get_tree().quit(1)
		if mode == "retry":
			# A later valid offer cannot undo a rejected attempt on this connection.
			api.send_auth(id, JSON.stringify({"format": "neptune.protocol/1", "versions": [2]}).to_utf8_buffer())
	)
	api.connected_to_server.connect(func():
		print("NEPTUNE_PROTOCOL_UNEXPECTED_ADMISSION")
		get_tree().quit(1)
	)
	api.peer_authentication_failed.connect(func(_id: int):
		if not attempted:
			get_tree().quit(1)
			return
		print("NEPTUNE_PROTOCOL_REJECTED mode=", mode)
		get_tree().quit(0)
	)
	api.connection_failed.connect(func(): get_tree().quit(1))
	get_tree().create_timer(6.0).timeout.connect(func():
		print("NEPTUNE_PROTOCOL_PROBE_TIMEOUT")
		get_tree().quit(1)
	)
	transport = ENetMultiplayerPeer.new()
	var config := preload("res://shared/runtime_config.gd").read()
	if transport.create_client("127.0.0.1", config.port) != OK:
		get_tree().quit(1)
		return
	api.multiplayer_peer = transport

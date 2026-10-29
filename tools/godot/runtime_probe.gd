extends Node

## Test the actual ClientMain/ServerMain transport owners, without login/gameplay.
func _ready() -> void:
	var client = get_node("/root/ClientMain")
	var incompatible := "--probe-incompatible" in OS.get_cmdline_user_args()
	if incompatible:
		# Isolated test process only; product configuration stays pinned to [1].
		client.protocol_gate._versions = [2]
		client.pending_initial_map = {"previous_session": true}
	client.connection_succeeded.connect(func():
		if incompatible or client.negotiated_protocol != 1 or client.protocol_gate.selected_version(1) != 1:
			push_error("Runtime probe connected without the supported protocol")
			get_tree().quit(1)
			return
		print("NEPTUNE_PROTOCOL_SELECTED=1")
		client._send_ping()
	)
	client.latency_updated.connect(func(_latency):
		print("NEPTUNE_RUNTIME_CONNECTED")
		get_tree().quit(0)
	)
	client.connection_failed.connect(func():
		if incompatible and client.last_connection_error == "incompatible_protocol_versions" and not client.connected and not client.authenticated and client.negotiated_protocol == 0 and client.pending_initial_map.is_empty():
			print("NEPTUNE_PROTOCOL_CLIENT_REFUSED=incompatible_protocol_versions")
			get_tree().quit(0)
			return
		push_error("Runtime probe could not connect")
		get_tree().quit(1)
	)
	get_tree().create_timer(5.0).timeout.connect(func():
		push_error("Runtime probe connection timeout")
		get_tree().quit(1)
	)
	client.connect_to_server("127.0.0.1")

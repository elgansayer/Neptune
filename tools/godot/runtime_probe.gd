extends Node

## Test the actual ClientMain/ServerMain transport owners, without login/gameplay.
func _ready() -> void:
	var client = get_node("/root/ClientMain")
	client.connection_succeeded.connect(func():
		client._send_ping()
	)
	client.latency_updated.connect(func(_latency):
		print("NEPTUNE_RUNTIME_CONNECTED")
		get_tree().quit(0)
	)
	client.connection_failed.connect(func():
		push_error("Runtime probe could not connect")
		get_tree().quit(1)
	)
	get_tree().create_timer(5.0).timeout.connect(func():
		push_error("Runtime probe connection timeout")
		get_tree().quit(1)
	)
	client.connect_to_server("127.0.0.1")

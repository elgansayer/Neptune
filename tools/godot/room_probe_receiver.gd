extends "res://shared/rpc_interface.gd"

var probe: Node
var index: int

func auth_response(data: Dictionary):
	probe.auth_received(index, data)

func receive_state(state: Dictionary):
	probe.state_received(index, state)

func receive_initial_map(data: Dictionary):
	probe.map_received(index, data)

func content_message(data: Dictionary):
	probe.content_received(index, data)

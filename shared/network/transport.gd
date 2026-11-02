extends RefCounted

## Native clients keep ENet by default. Browser deployments use the same Godot
## multiplayer/RPC protocol over a same-origin WebSocket reverse proxy.
static func server(kind: String, port: int, max_clients: int) -> Dictionary:
	if kind == "websocket":
		var socket := WebSocketMultiplayerPeer.new()
		socket.inbound_buffer_size = 1024 * 1024
		socket.outbound_buffer_size = 1024 * 1024
		return {"peer": socket, "error": socket.create_server(port)}
	var enet := ENetMultiplayerPeer.new()
	return {"peer": enet, "error": enet.create_server(port, max_clients)}

static func client(kind: String, address: String, port: int) -> Dictionary:
	if kind == "websocket":
		var url := address
		if OS.has_feature("web"):
			var location = JavaScriptBridge.get_interface("window").location
			url = ("wss://" if String(location.protocol) == "https:" else "ws://") + String(location.host) + "/ws"
		elif not url.begins_with("ws://") and not url.begins_with("wss://"):
			url = "ws://" + address + ":" + str(port)
		var socket := WebSocketMultiplayerPeer.new()
		socket.inbound_buffer_size = 1024 * 1024
		socket.outbound_buffer_size = 1024 * 1024
		return {"peer": socket, "error": socket.create_client(url)}
	var enet := ENetMultiplayerPeer.new()
	return {"peer": enet, "error": enet.create_client(address, port)}

extends Node

## Separate SceneMultiplayer/ENet clients in one bounded engine process. All
## authentication, admission, bots and snapshots come from actual ServerMain.
const Gate = preload("res://shared/network/protocol_negotiation.gd")
const Receiver = preload("res://tools/godot/room_probe_receiver.gd")
var humans := 12
var bots := 0
var seats := 12
var preset := 12
var port: int
var peers := []
var accepted := {}
var maps := {}
var snapshots := {}
var extra_started := false
var bots_requested := false
var refused := false
var finished := false
var policy_identity := {}
var auto_fill := false

func _ready() -> void:
	port = preload("res://shared/runtime_config.gd").read().port
	for arg in OS.get_cmdline_user_args():
		if arg == "--probe-auto-fill": auto_fill = true
		if arg.begins_with("--probe-humans="): humans = arg.get_slice("=", 1).to_int()
		if arg.begins_with("--probe-bots="): bots = arg.get_slice("=", 1).to_int()
		if arg.begins_with("--probe-preset="): preset = arg.get_slice("=", 1).to_int()
	seats = humans + bots
	var timeout := Timer.new()
	timeout.one_shot = true
	timeout.wait_time = 8.0
	timeout.timeout.connect(func(): fail("network room evidence timeout"))
	add_child(timeout)
	timeout.start()
	for index in range(humans): _create_peer(index)

func _create_peer(index: int) -> void:
	var branch := Node.new()
	branch.name = "Peer%d" % index
	add_child(branch)
	var api := SceneMultiplayer.new()
	get_tree().set_multiplayer(api, branch.get_path())
	var router = preload("res://shared/rpc_interface.gd").new()
	router.name = "ServerMain"
	branch.add_child(router)
	var receiver = Receiver.new()
	receiver.name = "ClientMain"
	receiver.probe = self
	receiver.index = index
	branch.add_child(receiver)
	var gate = Gate.new()
	branch.add_child(gate)
	if gate.configure(api) != OK:
		fail("probe gate configuration")
		return
	gate.rejected.connect(func(_id: int, reason: String): fail(reason))
	var peer := ENetMultiplayerPeer.new()
	if peer.create_client("127.0.0.1", port) != OK:
		fail("probe transport creation")
		return
	api.connected_to_server.connect(_connected.bind(index, router, api, gate))
	api.connection_failed.connect(func(): fail("transport connection failed"))
	peers.append({"api": api, "router": router, "gate": gate, "branch": branch})
	api.multiplayer_peer = peer

func _connected(index: int, router: Node, _api: SceneMultiplayer, gate: Node) -> void:
	if gate.selected_version(1) != 1:
		fail("missing actual negotiated version")
		return
	router.rpc_id(1, "authenticate_request", "CapacityProbe%d" % index, "fixture-password")

func auth_received(index: int, data: Dictionary) -> void:
	if index == humans:
		if data.get("success", true) or data.get("error", "") != "room_full":
			fail("extra transport peer was not clearly refused at room admission")
			return
		refused = true
	else:
		if not data.get("success", false) or data.get("room", {}).get("seats", 0) != seats:
			fail("supported human auth/admission failed")
			return
		accepted[index] = true
		if accepted.size() == humans:
			if bots > 0 and not bots_requested and not auto_fill:
				bots_requested = true
				for _bot in range(bots): peers[0].router.rpc_id(1, "spawn_bot_request", "BALANCED")
			elif bots == 0: _start_extra()
	_check_complete()

func map_received(index: int, data: Dictionary) -> void:
	if index == humans:
		fail("refused peer received a map")
		return
	if data.get("room", {}).get("seats", 0) != seats or data.get("map_width", 0) != 17 or data.get("map_height", 0) != 13:
		fail("initial map/capacity contract mismatch")
		return
	maps[index] = true
	_check_complete()

func state_received(index: int, state: Dictionary) -> void:
	if index == humans:
		fail("refused peer received gameplay state")
		return
	var roster: Dictionary = state.get("p", {})
	var capacity: Dictionary = state.get("room", {})
	if roster.size() != seats or not state.get("a", false): return # Require the real countdown/round start.
	var policy := {"bot_policy": capacity.get("bot_policy", ""), "bot_policy_seed": capacity.get("bot_policy_seed", "")}
	if policy.bot_policy != "neptune-heuristic-rng-v1" or not str(policy.bot_policy_seed).is_valid_int() or (not policy_identity.is_empty() and policy_identity != policy):
		fail("missing/inconsistent policy identity for repeatable evidence")
		return
	policy_identity = policy
	if auto_fill:
		var fill: Dictionary = capacity.get("bot_fill", {})
		if fill.get("target", 0) != seats or fill.get("personality", "") != "DEFENSIVE" or not fill.get("applied", false):
			fail("automatic fill policy was not applied at the round boundary")
			return
	if capacity.get("seats", 0) != seats or capacity.get("preset_limit", 0) != preset or capacity.get("protocol_limit", 0) != 12 or capacity.get("occupied", 0) != seats or capacity.get("humans", 0) != humans or capacity.get("bots", 0) != bots:
		fail("authoritative capacity/participant metadata mismatch")
		return
	var bot_count := 0
	var positions := {}
	for id in roster:
		if str(id).to_int() < 0: bot_count += 1
		positions[str(roster[id].get("p"))] = true
		if auto_fill:
			var participant: Dictionary = capacity.get("participants", {}).get(str(id), {})
			var bot: bool = str(id).to_int() < 0
			if participant.get("type", "") != ("bot" if bot else "human") or (bot and participant.get("personality", "") != "DEFENSIVE"):
				fail("missing/inconsistent explicit bot participant metadata")
				return
	if bot_count != bots or not roster.has(str(peers[index].api.get_unique_id())) or positions.size() != seats:
		fail("actual roster identities/positions disagree with room metadata")
		return
	snapshots[index] = true
	_start_extra()
	_check_complete()

func _start_extra() -> void:
	if not extra_started:
		extra_started = true
		_create_peer(humans)

func _check_complete() -> void:
	if finished or not refused or accepted.size() != humans or maps.size() != humans or snapshots.size() != humans: return
	finished = true
	var receipt := {"seats": seats, "humans": humans, "bots": bots, "preset_limit": preset, "protocol_limit": 12, "accepted": accepted.size(), "refused": 1, "snapshots": snapshots.size(), "maps": maps.size(), "active": true}
	receipt.merge(policy_identity)
	if auto_fill: receipt["auto_fill"] = true
	print("NEPTUNE_ROOM_CAPACITY=", JSON.stringify(receipt))
	for entry in peers: entry.api.multiplayer_peer.close()
	get_tree().quit(0)

func fail(reason: String) -> void:
	if finished: return
	finished = true
	print("NEPTUNE_ROOM_PROBE_FAILED=", reason)
	get_tree().quit(1)

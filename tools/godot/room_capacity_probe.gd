extends Node

## Separate SceneMultiplayer/ENet clients in one bounded engine process. All
## authentication, admission, bots and snapshots come from actual ServerMain.
const Gate = preload("res://shared/network/protocol_negotiation.gd")
const Receiver = preload("res://tools/godot/room_probe_receiver.gd")
const Download = preload("res://shared/network/content_download.gd")
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
var spectator_authenticated := false
var spectator_map := false
var spectator_snapshot := false
var finished := false
var policy_identity := {}
var auto_fill := false
var expected_personality := "DEFENSIVE"
var expected_width := 17
var expected_height := 13
var expected_content: Dictionary = {}
var expected_selection_count := 2
var expected_lock: Dictionary = {}
var expected_lock_sha256 := ""

func _process(_delta: float) -> void:
	for entry in peers: entry.download.tick()

func _ready() -> void:
	port = preload("res://shared/runtime_config.gd").read().port
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--probe-content-json="):
			var parsed = JSON.parse_string(arg.trim_prefix("--probe-content-json="))
			if not parsed is Dictionary or parsed.is_empty():
				fail("invalid expected content descriptor")
				return
			expected_content = parsed
		if arg.begins_with("--probe-lock-json="):
			var parsed = JSON.parse_string(arg.trim_prefix("--probe-lock-json="))
			if not parsed is Dictionary or parsed.is_empty():
				fail("invalid expected manifest lock")
				return
			expected_lock = parsed
		if arg.begins_with("--probe-lock-sha256="):
			expected_lock_sha256 = arg.trim_prefix("--probe-lock-sha256=")
		if arg.begins_with("--probe-selection-count="):
			expected_selection_count = arg.get_slice("=", 1).to_int()
		if arg == "--probe-auto-fill": auto_fill = true
		if arg.begins_with("--probe-personality="): expected_personality = arg.get_slice("=", 1)
		if arg.begins_with("--probe-map-width="): expected_width = arg.get_slice("=", 1).to_int()
		if arg.begins_with("--probe-map-height="): expected_height = arg.get_slice("=", 1).to_int()
		if arg.begins_with("--probe-humans="): humans = arg.get_slice("=", 1).to_int()
		if arg.begins_with("--probe-bots="): bots = arg.get_slice("=", 1).to_int()
		if arg.begins_with("--probe-preset="): preset = arg.get_slice("=", 1).to_int()
	if not expected_content.is_empty() and (expected_lock.is_empty() or expected_lock_sha256.length() != 64
		or expected_selection_count < 1 or expected_selection_count > 32):
		fail("registered arena probe requires its complete expected manifest lock")
		return
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
	var download = Download.new("user://capacity-content-peer-%d" % index)
	download.outbound.connect(func(message: Dictionary): router.rpc_id(1, "content_message", message))
	download.status_changed.connect(func(result: Dictionary):
		if not result.get("accepted", true): fail("registered arena content download refused: " + result.reason)
	)
	peers.append({"api": api, "router": router, "gate": gate, "branch": branch, "download": download})
	api.multiplayer_peer = peer

func _connected(index: int, router: Node, _api: SceneMultiplayer, gate: Node) -> void:
	if gate.selected_version(1) != 3:
		fail("missing actual negotiated version")
		return
	router.rpc_id(1, "authenticate_request", "CapacityProbe%d" % index, "fixture-password")

func content_received(index: int, message: Dictionary) -> void:
	var download = peers[index].download
	if message.get("type", "") == "offer":
		download.begin(message)
	elif message.get("type", "") == "chunk":
		download.receive(message)
	else:
		fail("registered arena received unsupported content message")

func auth_received(index: int, data: Dictionary) -> void:
	if index == humans:
		if bots > 0:
			if not data.get("success", false) or not peers[index].api.get_unique_id() in data.get("room", {}).get("spectators", []):
				fail("late human did not receive explicit capacity-safe spectator admission")
				return
			spectator_authenticated = true
		else:
			if data.get("success", true) or data.get("error", "") != "room_full":
				fail("extra transport peer was not clearly refused at room admission")
				return
			refused = true
	else:
		if not data.get("success", false) or data.get("room", {}).get("seats", 0) != seats:
			fail("supported human auth/admission failed")
			return
		if not expected_content.is_empty() and peers[index].download.receipt().get("state", "") != "ready":
			fail("registered arena admitted before production download helper verified readiness")
			return
		accepted[index] = true
		if accepted.size() == humans:
			if bots > 0 and not bots_requested and not auto_fill:
				bots_requested = true
				for _bot in range(bots): peers[0].router.rpc_id(1, "spawn_bot_request", "BALANCED")
			elif bots == 0: _start_extra()
	_check_complete()

func map_received(index: int, data: Dictionary) -> void:
	if index == humans and bots == 0:
		fail("refused peer received a map")
		return
	if data.get("room", {}).get("seats", 0) != seats or data.get("map_width", 0) != expected_width or data.get("map_height", 0) != expected_height or data.get("map_config", {}).get("render_geometry", false) != true:
		fail("initial map/capacity contract mismatch")
		return
	if not expected_content.is_empty():
		var verified: Dictionary = peers[index].download.validate_initial_map(data)
		if not verified.accepted:
			fail("registered arena initial map failed production content validation: " + verified.reason)
			return
		var config: Dictionary = data.get("map_config", {})
		var selection = config.get("selection", [])
		if config.get("content", {}) != expected_content or not selection is Array or selection.size() != expected_selection_count:
			fail("initial map did not carry the selected additive arena identity")
			return
		if config.get("lock", {}) != expected_lock or config.get("lock_sha256", "") != expected_lock_sha256 or selection != expected_lock.get("packs", []):
			fail("initial map did not carry the exact portable manifest lock and selected identities")
			return
		if JSON.stringify(config.lock, "", true).sha256_text() != expected_lock_sha256:
			fail("received manifest lock digest disagrees with its canonical bytes")
			return
		if "res://" in JSON.stringify(config) or "user://" in JSON.stringify(config):
			fail("public content descriptor leaked local source paths")
			return
	elif data.get("map_config", {}).has("lock") or data.get("map_config", {}).has("lock_sha256"):
		fail("legacy room unexpectedly acquired a pack lock")
		return
	if index == humans:
		spectator_map = true
	else:
		maps[index] = true
	_check_complete()

func state_received(index: int, state: Dictionary) -> void:
	if index == humans:
		if bots == 0:
			fail("refused peer received gameplay state")
			return
		var id: int = peers[index].api.get_unique_id()
		if state.get("round", {}).get("phase", "") != "active": return
		if not id in state.get("room", {}).get("spectators", []) or state.get("p", {}).has(str(id)) or state.get("p", {}).size() != seats:
			fail("late spectator changed the live roster or lacked explicit waiting metadata")
			return
		spectator_snapshot = true
		_check_complete()
		return
	if not expected_content.is_empty() and peers[index].download.receipt().get("state", "") != "ready":
		fail("registered arena state arrived before content readiness")
		return
	var roster: Dictionary = state.get("p", {})
	var capacity: Dictionary = state.get("room", {})
	if roster.size() != seats or not state.get("a", false): return # Require the real countdown/round start.
	var policy := {"bot_policy": capacity.get("bot_policy", ""), "bot_policy_seed": capacity.get("bot_policy_seed", "")}
	if policy.bot_policy != "neptune-heuristic-v3" or not str(policy.bot_policy_seed).is_valid_int() or (not policy_identity.is_empty() and policy_identity != policy):
		fail("missing/inconsistent policy identity for repeatable evidence")
		return
	policy_identity = policy
	if auto_fill:
		var fill: Dictionary = capacity.get("bot_fill", {})
		if fill.get("target", 0) != seats or fill.get("personality", "") != expected_personality or not fill.get("applied", false):
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
			if participant.get("type", "") != ("bot" if bot else "human") or (bot and participant.get("personality", "") != expected_personality):
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
	var extra_verified := (spectator_authenticated and spectator_map and spectator_snapshot) if bots > 0 else refused
	if finished or not extra_verified or accepted.size() != humans or maps.size() != humans or snapshots.size() != humans: return
	finished = true
	var receipt := {"seats": seats, "humans": humans, "bots": bots, "preset_limit": preset, "protocol_limit": 12, "accepted": accepted.size(), "refused": 0 if bots > 0 else 1, "spectators": 1 if bots > 0 else 0, "snapshots": snapshots.size(), "maps": maps.size(), "active": true}
	receipt.merge(policy_identity)
	if auto_fill: receipt["auto_fill"] = true
	if not expected_content.is_empty():
		receipt["content"] = expected_content.duplicate(true)
		receipt["selection"] = expected_lock.packs.duplicate(true)
		receipt["lock"] = expected_lock.duplicate(true)
		receipt["lock_sha256"] = expected_lock_sha256
	print("NEPTUNE_ROOM_CAPACITY=", JSON.stringify(receipt))
	for entry in peers: entry.api.multiplayer_peer.close()
	get_tree().quit(0)

func fail(reason: String) -> void:
	if finished: return
	finished = true
	print("NEPTUNE_ROOM_PROBE_FAILED=", reason)
	get_tree().quit(1)

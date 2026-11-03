@tool
extends BTAction
class_name BTThrowBomb

const SimulationTime = preload("res://shared/ai/simulation_time.gd")
const ThrowPlan = preload("res://shared/ai/planning/throw_plan.gd")

enum ThrowState { IDLE, PLACING, PICKING_UP, THROWING }
@export var recovery_only := false
@export var preparation_timeout_msec := 1200.0
var _state: ThrowState = ThrowState.IDLE
var _deadline := 0.0

func _generate_name() -> String:
	return "Recover Committed Throw" if recovery_only else "Prepare And Throw Via Validated Commands"

func _enter() -> void:
	_state = ThrowState.PLACING if recovery_only else ThrowState.IDLE
	_deadline = SimulationTime.milliseconds(blackboard) + clampf(preparation_timeout_msec, 100.0, 2000.0)

func _tick(_delta: float) -> int:
	var player = blackboard.get_var("player", null)
	var world = blackboard.get_var("game_instance", null)
	var sampler = blackboard.get_var("grid_sampler", null)
	if not is_instance_valid(player) or world == null or sampler == null: return FAILURE
	var recovery: Dictionary = blackboard.get_var("throw_recovery", {}, false)
	if recovery_only:
		if recovery.is_empty(): return FAILURE
		_deadline = float(recovery.deadline)
		if not player.is_carrying_bomb() or not player.has_method("public_data") or str(player.public_data().get("carried_bomb_id", "")) != str(recovery.bomb_id):
			return _fail(player, "recovery_actor_or_bomb_changed")
	elif blackboard.get_var("tactical_plan", "NONE") != "POWER_THROW":
		return FAILURE
	if player.is_dead or not player.has_power_glove:
		return _fail(player, "throw_ability_unavailable")
	# A new goal gets its ordinary strategy delay and an initial preparation
	# tick. No placement occurs until real physics has supplied its facing.
	if _state == ThrowState.IDLE:
		_state = ThrowState.PLACING
		return RUNNING
	if not world.match_active:
		return _fail(player, "match_inactive")
	if SimulationTime.milliseconds(blackboard) >= _deadline:
		return _fail(player, "throw_preparation_timeout")
	if recovery_only and int(recovery.attempts) >= 3:
		return _fail(player, "throw_recovery_exhausted")
	var direction: Vector2 = recovery.get("direction", Vector2.ZERO) if recovery_only else blackboard.get_var("throw_direction", Vector2.ZERO, false)
	var target: Vector2i = blackboard.get_var("throw_target", ThrowPlan.INVALID_TARGET, false)
	var requires_target: bool = not player.is_carrying_bomb()
	var plan: Dictionary = ThrowPlan.choose(player, world, sampler, target, direction, requires_target)
	if not plan.get("supported", false) and recovery_only:
		# Releasing a committed carried bomb may use another publicly safe
		# direction; it does not start a new offensive goal or grant new stats.
		plan = ThrowPlan.choose(player, world, sampler, ThrowPlan.INVALID_TARGET, Vector2.ZERO, false)
	if not plan.get("supported", false):
		return _fail(player, plan.get("reason", "unsafe_throw"), recovery_only)
	direction = plan.direction
	if player.last_move_direction != direction:
		var facing: Dictionary = player.set_input(direction.x, direction.y)
		return RUNNING if facing.accepted else _fail(player, facing.reason, recovery_only)
	player.set_input(0, 0)
	# The same legal human commands may be submitted synchronously. Perform
	# no physics/animation/fuse/state mutation between them. This avoids a
	# planted-own-bomb frame preempting pickup in the hazard-first tree.
	if not player.is_carrying_bomb():
		var bomb = _at_feet(player, world)
		if bomb == null:
			var placed: Dictionary = world.place_bomb(player)
			if not placed.accepted:
				blackboard.set_var("last_bomb_rejection", placed.reason)
				return _fail(player, placed.reason)
			bomb = world.bombs.get(placed.bomb_ids[0])
		if bomb == null or bomb.has_exploded:
			return _fail(player, "throw_bomb_unavailable")
		_state = ThrowState.PICKING_UP
		if not player.try_pickup_bomb(bomb):
			return _fail(player, "pickup_refused")
		blackboard.set_var("last_throw_preparation_bomb", str(bomb.bomb_id))
	_state = ThrowState.THROWING
	if not player.throw_carried_bomb():
		var public: Dictionary = player.public_data() if player.has_method("public_data") else {}
		var id := str(public.get("carried_bomb_id", ""))
		if not id.is_empty():
			blackboard.set_var("throw_recovery", {"bomb_id": id, "direction": direction,
				"deadline": _deadline, "attempts": int(recovery.get("attempts", 0)) + 1})
		return _fail(player, "throw_refused", not id.is_empty())
	blackboard.set_var("last_throw_time", SimulationTime.milliseconds(blackboard))
	blackboard.set_var("last_throw_plan", plan)
	blackboard.set_var("throw_recovery", {})
	blackboard.set_var("last_throw_failure", "")
	blackboard.set_var("tactical_plan", "NONE")
	return SUCCESS

func _fail(player, reason: String, retain_recovery: bool = false) -> int:
	player.set_input(0, 0)
	blackboard.set_var("last_throw_failure", reason)
	if not retain_recovery: blackboard.set_var("throw_recovery", {})
	return FAILURE

func _at_feet(player, world):
	for bomb in world.bombs.values():
		if is_instance_valid(bomb) and not bomb.has_exploded and bomb.bomb_state == ServerBomb.BombState.PLANTED and bomb.get_tile_position() == player.get_tile_position():
			return bomb
	return null

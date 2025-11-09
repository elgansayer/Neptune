# AI Upgrade Guide: Phase 1-7 Implementation

**Objective:** Transform AI from idle/reactive to "10× smarter, 30× more aggressive, 50× more item-focused, 60× more cunning" through systematic 7-phase overhaul.

---

## Overview

This upgrade replaces tile-based snapshot danger detection with **continuous real-time threat assessment**, expands action repertoire from 10→16 actions, adds **predictive bomb planning**, implements **smooth free-movement navigation**, and introduces **adaptive opponent profiling** with behavior role detection.

### Architecture Layers

1. **DangerMapper** (`danger_mapper.gd`) — Real-time threat field with per-tick countdown heatmap
2. **UtilityScorer** (`utility_scorer.gd`) — Multi-criteria action evaluation with 16 action types
3. **BombPlanner** (`bomb_planner.gd`) — Safe placement with trajectory prediction
4. **ImprovedAIController** (`improved_ai_controller.gd`) — High-level coordination + adaptive profiling
5. **AIDebugVisualizer** (`ai_debug_visualizer.gd`) — Visual overlays for debugging

---

## Phase 1: Diagnostics & Logging

### Purpose
Establish performance baselines and identify bottlenecks before optimization.

### DangerMapper Additions
```gdscript
# Toggle diagnostics
var debug_enabled: bool = false

# Performance tracking
var debug_update_time_ms: float = 0.0
var debug_prediction_time_ms: float = 0.0
var debug_query_count: int = 0
var debug_cache_hits: int = 0

# Bomb lifetime tracking
var bomb_lifetime_tracker: Dictionary = {}
```

**Key Metrics:**
- Update time (target <2ms per frame)
- Cache hit rate (target >70%)
- Query frequency per AI decision

### ImprovedAIController Additions
```gdscript
# Action distribution tracking
var debug_action_distribution: Dictionary = {}
var debug_decision_count: int = 0
var debug_emergency_count: int = 0
var debug_last_log_time: float = 0.0
const DEBUG_LOG_INTERVAL: float = 5.0
```

**Logged Data:**
- Most common action types (track idle loops)
- Emergency trigger frequency
- Decision cadence (Hz)

---

## Phase 2: Continuous Danger Field

### Problem: Old System
- Snapshot-based with discrete "zones"
- No temporal prediction beyond current frame
- Missed chain reactions and explosion echoes

### Solution: Per-Tick Countdown Heatmap
```gdscript
# Old: danger_zones: Dictionary (static)
# New:
var danger_heatmap: Dictionary = {}  # tile_key → {explosion_countdowns: Array}
var explosion_echoes: Dictionary = {}  # Fading danger after blasts
var chain_prediction_cache: Dictionary = {}
```

**Heatmap Structure:**
```gdscript
danger_heatmap["5,7"] = {
	"explosion_countdowns": [120, 45, 180],  # Ticks until explosions
	"bomb_ids": [bomb_ref1, bomb_ref2, bomb_ref3]
}
```

**Danger Calculation:**
```gdscript
func get_danger_at_tile(tile: Vector2i, current_time: float, lookahead: float) -> float:
	var key = "%d,%d" % [tile.x, tile.y]
	var tile_data = danger_heatmap.get(key, {})
	var max_danger = 0.0
	var lookahead_ticks = int(lookahead * 60.0)
	
	for countdown in tile_data.get("explosion_countdowns", []):
		if countdown <= lookahead_ticks:
			var urgency = clamp(1.0 - (countdown / 180.0), 0.0, 1.0)
			max_danger = max(max_danger, urgency)
	
	# Add echo danger
	var echo = explosion_echoes.get(key, {"intensity": 0.0})
	max_danger = max(max_danger, echo.intensity)
	
	return max_danger
```

### New Query Methods
- `get_peak_danger_path(path: Array) → float` — Max danger along route
- `sample_cone_danger(origin: Vector2i, direction: Vector2, arc: float) → float` — Directional threat
- `get_area_danger(center: Vector2i, radius: int) → float` — Regional average
- `get_danger_gradient(tile: Vector2i) → Vector2` — Escape direction hint
- `is_direction_safe(tile: Vector2i, direction: Vector2, steps: int) → bool` — Path validation

**Chain Prediction:**
```gdscript
func _predict_chain_reactions(bomb: Node2D, affected_tiles: Array, current_time: float) → void:
	for tile in affected_tiles:
		for other_bomb_id in bomb_lifetime_tracker:
			var other_bomb = game_instance.bombs.get(other_bomb_id)
			if other_bomb and other_bomb.get_tile_position() == tile:
				# Chain trigger detected
				var new_explosion_time = current_time + bomb.fuse_time
				_register_secondary_explosion(other_bomb, new_explosion_time)
```

---

## Phase 3: Expanded Action Repertoire

### New Actions
Added 4 tactical actions to break idle loops:

1. **FLANK_OPPONENT** — Circle around target's rear
2. **KITE_DANGER** — Maintain safe distance while harassing
3. **EXPLORE_MAP** — Anti-idle exploration when no threats
4. **CONTROL_CENTER** — Contest strategic map positions

### Hysteresis & Cooldowns
```gdscript
var action_cooldowns: Dictionary = {}
const COOLDOWN_DURATION: float = 1.5

func _apply_cooldowns(scores: Array, current_time: float) → Array:
	for action_dict in scores:
		var action_type = action_dict.get("action", -1)
		var last_used = action_cooldowns.get(action_type, 0.0)
		if current_time - last_used < COOLDOWN_DURATION:
			action_dict.score *= 0.3  # Heavy penalty
	return scores
```

**Prevents oscillation** between similar-scored actions.

### Idle Penalty
```gdscript
var last_position: Vector2 = Vector2.ZERO
var idle_penalty_multiplier: float = 1.0
const MAX_IDLE_PENALTY: float = 0.15

func _track_idle_behavior(current_pos: Vector2, delta_time: float):
	if current_pos.distance_to(last_position) < 5.0:
		idle_penalty_multiplier -= 0.1 * delta_time
		idle_penalty_multiplier = max(idle_penalty_multiplier, MAX_IDLE_PENALTY)
	else:
		idle_penalty_multiplier = 1.0
	last_position = current_pos
```

**Degrades scores** when bot stands still.

### Guaranteed Fallback
```gdscript
func _generate_fallback_action(tile: Vector2i, current_time: float) → Dictionary:
	# BFS for nearest safe tile
	var frontier = [tile]
	var visited = {"%d,%d" % [tile.x, tile.y]: true}
	
	while not frontier.is_empty():
		var current = frontier.pop_front()
		var danger = danger_mapper.get_danger_at_tile(current, current_time, 1.0)
		if danger < 0.2:
			return {
				"score": 25.0,  # Non-zero baseline
				"action": ActionType.EXPLORE_MAP,
				"target_tile": current
			}
		# Expand neighbors...
	
	# Last resort: random wander
	return {"score": 10.0, "action": ActionType.EXPLORE_MAP, "target_tile": tile}
```

---

## Phase 4: Predictive Bomb Planning

### Opponent Trajectory Prediction
```gdscript
var opponent_trajectories: Dictionary = {}

func _update_opponent_trajectories(current_time: float):
	for player_id in game_instance.players:
		var player = game_instance.players[player_id]
		var position = player.position
		var velocity = observer.get_recent_velocity(player_id)
		
		opponent_trajectories[player_id] = {
			"position": position,
			"velocity": velocity,
			"predicted_tile": _extrapolate_tile(position, velocity, 1.0)
		}

func _extrapolate_tile(pos: Vector2, vel: Vector2, seconds: float) → Vector2i:
	var future_pos = pos + vel * seconds
	return Vector2i(
		int(future_pos.x / Constants.TILE_SIZE),
		int(future_pos.y / Constants.TILE_SIZE)
	)
```

### Trap Evaluation
```gdscript
func evaluate_trap_placement(ai_tile: Vector2i, target_tile: Vector2i) → float:
	# Check if target is cornered
	var escape_routes = danger_mapper.calculate_escape_routes(target_tile, current_time)
	if escape_routes.safe_count <= 1:
		return 50.0  # High trap value
	
	# Predict if target will walk into blast radius
	var trajectory = opponent_trajectories.get(target_id, {})
	var predicted_tile = trajectory.get("predicted_tile", target_tile)
	var bomb_affected = danger_mapper.simulate_bomb_placement(ai_tile, bomb_range, current_time)
	
	if predicted_tile in bomb_affected.affected_tiles:
		return 35.0
	
	return 0.0
```

### Adaptive Risk Thresholds
```gdscript
var risk_tolerance: float = 0.5  # 0.0=cautious, 1.0=reckless
var min_escape_buffer: float = 1.5  # Seconds

func can_place_bomb_safely(tile: Vector2i, current_time: float) → Dictionary:
	var escape_time = _calculate_escape_time(tile)
	var required_buffer = lerp(min_escape_buffer, 0.8, risk_tolerance)
	
	if escape_time < required_buffer:
		return {"safe": false, "reason": "insufficient_escape_time"}
	
	# Check ally bomb overlap
	if _check_ally_bomb_overlap(tile):
		return {"safe": false, "reason": "ally_bomb_conflict"}
	
	return {"safe": true, "escape_tile": best_escape_tile}
```

---

## Phase 5: Hybrid Navigation

### Problem: Jerky A* Movement
Tile-based pathfinding produces stutter-step motion unsuitable for free-movement physics.

### Solution: Steering + Replanning
```gdscript
var target_velocity: Vector2 = Vector2.ZERO
var current_velocity: Vector2 = Vector2.ZERO
var steering_force: Vector2 = Vector2.ZERO
const MAX_STEERING_FORCE: float = 400.0
const VELOCITY_SMOOTHING: float = 0.15
const ARRIVAL_RADIUS: float = 8.0
```

**Steering Calculation:**
```gdscript
func _calculate_steering(target_tile: Vector2i, ai_player: Node2D) → Vector2:
	var target_pos = Vector2(
		target_tile.x * Constants.TILE_SIZE + Constants.TILE_SIZE * 0.5,
		target_tile.y * Constants.TILE_SIZE + Constants.TILE_SIZE * 0.5
	)
	
	var to_target = target_pos - ai_player.position
	var distance = to_target.length()
	
	if distance < 1.0:
		return Vector2.ZERO
	
	# Arrival behavior: slow down near target
	var desired_speed = ai_player.speed
	if distance < ARRIVAL_RADIUS:
		desired_speed *= (distance / ARRIVAL_RADIUS)
	
	var desired_velocity = to_target.normalized() * desired_speed
	var force = (desired_velocity - current_velocity)
	
	# Limit acceleration
	if force.length() > MAX_STEERING_FORCE:
		force = force.normalized() * MAX_STEERING_FORCE
	
	# Smooth velocity changes
	target_velocity = current_velocity + force
	current_velocity = current_velocity.lerp(target_velocity, VELOCITY_SMOOTHING)
	
	return current_velocity.normalized()
```

### Replanning Triggers
```gdscript
func _check_replanning_triggers(current_time: float) → bool:
	# Bomb spawn detection
	var current_bomb_count = game_instance.bombs.size()
	if current_bomb_count != last_bomb_count:
		last_bomb_count = current_bomb_count
		return true
	
	# Danger spike detection
	var my_tile = ai_player.get_tile_position()
	var current_danger = danger_mapper.get_danger_at_tile(my_tile, current_time, 1.0)
	var last_danger = last_danger_snapshot.get(my_tile, 0.0)
	
	if current_danger - last_danger > DANGER_SPIKE_THRESHOLD:
		last_danger_snapshot[my_tile] = current_danger
		return true
	
	return false
```

**Prevents stale paths** when bombs spawn near AI.

---

## Phase 6: Adaptive Opponent Profiling

### Power Gap Analysis
```gdscript
func _calculate_power_gaps(ai_player: Node2D) → Dictionary:
	var my_power = _calculate_power_score(ai_player)
	var gaps: Dictionary = {}
	
	for player_id in opponent_profiles.keys():
		var profile = opponent_profiles[player_id]
		var opponent_power = profile.power_level
		gaps[player_id] = {
			"gap": opponent_power - my_power,
			"ratio": opponent_power / max(0.1, my_power),
			"advantage": my_power > opponent_power
		}
	
	return gaps

func _calculate_power_score(player: Node2D) → float:
	return (player.max_bombs * 0.6 + 
	        player.bomb_range * 0.45 + 
	        player.speed_multiplier * 0.4)
```

**Weight Adjustments:**
```gdscript
func _apply_power_gap_biases(power_gaps: Dictionary) → Dictionary:
	var avg_gap = 0.0
	for gap_data in power_gaps.values():
		avg_gap += gap_data.gap
	avg_gap /= max(1, power_gaps.size())
	
	var weights = {"item_focus": 1.0, "aggression": 1.0, "retreat": 1.0, "trap": 1.0}
	
	# Outmatched: prioritize items
	if avg_gap > 2.0:
		weights.item_focus = 2.8
		weights.aggression = 0.4
		weights.retreat = 1.6
	
	# Dominant: aggressive trapping
	elif avg_gap < -2.0:
		weights.item_focus = 0.6
		weights.aggression = 2.5
		weights.trap = 2.2
	
	return weights
```

### Behavior Role Detection
Classifies opponents based on observed patterns:

**Roles:**
- **Pressurer:** High aggression + frequent bombs
- **Trapper:** Strategic placement + moderate aggression
- **Item-Hog:** Pickup focus + low confrontation

```gdscript
func _classify_behavior_roles():
	for player_id in opponent_profiles.keys():
		var profile = opponent_profiles[player_id]
		var window = max(1.0, profile.observation_window)
		
		var bomb_rate = profile.bomb_placements / window
		var item_rate = profile.item_pickups / window
		var aggression_rate = profile.aggressive_moves / window
		
		var role = "balanced"
		
		if aggression_rate > 2.0 and bomb_rate > 1.5:
			role = "pressurer"
		elif bomb_rate > 1.0 and aggression_rate < 1.5:
			role = "trapper"
		elif item_rate > 1.2 and aggression_rate < 0.8:
			role = "item_hog"
		
		profile.behavior_role = role
```

**Counter-Play Adjustments:**
```gdscript
func _get_role_modifier(action_type: int, target_role: String, confidence: float) → float:
	match action_type:
		ActionType.RETREAT:
			if target_role == "pressurer":
				return lerp(1.0, 1.8, confidence)
		ActionType.ATTACK_PLAYER:
			if target_role == "item_hog":
				return lerp(1.0, 2.0, confidence)
			elif target_role == "pressurer":
				return lerp(1.0, 0.6, confidence)
		ActionType.KITE_DANGER:
			if target_role == "pressurer":
				return lerp(1.0, 2.2, confidence)
	return 1.0
```

---

## Phase 7: Debug Visualizations

### Heatmap Overlay
```gdscript
func _draw_danger_zones(current_time: float):
	for tile_key in danger_mapper.danger_heatmap.keys():
		var tile_data = danger_heatmap[tile_key]
		var peak_danger = 0.0
		var earliest_explosion = INF
		
		for countdown in tile_data.explosion_countdowns:
			var time_until = countdown / 60.0
			peak_danger = max(peak_danger, clamp(1.0 - countdown / 180.0, 0.0, 1.0))
			earliest_explosion = min(earliest_explosion, time_until)
		
		# Color by urgency
		var color = COLOR_HIGH_DANGER if earliest_explosion < 0.5 else COLOR_MEDIUM_DANGER
		color.a = peak_danger * 0.6
		
		draw_rect(Rect2(tile_world_pos, tile_size), color)
```

### Opponent Role Badges
```gdscript
func _draw_opponent_roles():
	for profile in ai_controller.opponent_profiles.values():
		var role = profile.behavior_role
		var role_color = Color.RED if role == "pressurer" else Color.ORANGE
		
		# Confidence ring
		draw_arc(opponent_pos, 30.0, 0, TAU * profile.role_confidence, 32, role_color, 2.5)
		
		# Role label
		draw_string(font, label_pos, role.substr(0, 3).to_upper(), role_color)
```

### Toggle Commands
```gdscript
debug_visualizer.toggle_danger_zones()  # Heatmap overlay
debug_visualizer.toggle_paths()         # Pathfinding lines
debug_visualizer.toggle_targets()       # Crosshairs on objectives
debug_visualizer.toggle_reasoning()     # Text labels above AI
```

---

## Tuning Parameters

### Personality Weights (per-AI)
```gdscript
personality_weights = {
	"aggression": 800,        # 30× more aggressive (was ~27)
	"item_focus": 1200,       # 50× more item-focused (was ~24)
	"trap_bonus": 900,        # 60× more cunning (was ~15)
	"reaction_delay": 0.08,   # Faster reflexes (was 0.15)
	"risk_tolerance": 0.65    # Balanced caution
}
```

### Global Constants
```gdscript
# DangerMapper
const EXPLOSION_ECHO_DURATION: float = 1.5
const CHAIN_PREDICTION_DEPTH: int = 3
const DANGER_QUERY_CACHE_SIZE: int = 256

# UtilityScorer
const COOLDOWN_DURATION: float = 1.5
const MIN_ACTION_SCORE: float = 5.0
const IDLE_PENALTY_RATE: float = 0.1

# BombPlanner
const MIN_ESCAPE_BUFFER: float = 1.5
const TRAP_PREDICTION_WINDOW: float = 1.0

# Navigation
const MAX_STEERING_FORCE: float = 400.0
const VELOCITY_SMOOTHING: float = 0.15
const ARRIVAL_RADIUS: float = 8.0
const DANGER_SPIKE_THRESHOLD: float = 0.3
```

---

## Performance Targets

| Metric | Target | Critical |
|--------|--------|----------|
| Danger update time | <2ms | <5ms |
| Decision frequency | 10 Hz | 5 Hz |
| Cache hit rate | >70% | >50% |
| Emergency escapes | <20% actions | <40% |
| Idle frames | 0% | <5% |

**Monitor via:**
```gdscript
if debug_enabled:
	print("Update: %.2fms | Queries: %d | Cache: %.1f%%" % [
		debug_update_time_ms,
		debug_query_count,
		(debug_cache_hits / float(max(1, debug_query_count))) * 100.0
	])
```

---

## Testing Checklist

### Phase Validation
- [ ] Phase 1: Diagnostics log without crashes for 5min gameplay
- [ ] Phase 2: Heatmap visualizer shows overlapping explosions
- [ ] Phase 3: AI never idles for >2s, fallback action always fires
- [ ] Phase 4: AI places traps when opponents are cornered
- [ ] Phase 5: Movement is smooth with no stutter-stepping
- [ ] Phase 6: Role badges appear after 10s observation window
- [ ] Phase 7: Debug overlays toggle without performance drop

### Combat Scenarios
1. **1v1 Item Race:** AI should collect 80% of powerups when outmatched
2. **Trap Execution:** AI traps static opponent within 3 attempts
3. **Pressure Response:** AI retreats from "pressurer" opponents >60% of time
4. **Chain Reaction:** AI avoids chaining own bombs (zero self-kills from chains)

---

## Troubleshooting

### AI Still Idle
- Check `debug_action_distribution` for zero-score actions
- Verify `_generate_fallback_action` is called
- Ensure `idle_penalty_multiplier` is decreasing

### Jerky Movement
- Increase `VELOCITY_SMOOTHING` (0.15 → 0.25)
- Lower `MAX_STEERING_FORCE` (400 → 300)
- Check `_check_replanning_triggers` isn't firing every frame

### Low Cache Hit Rate
- Reduce `DANGER_QUERY_CACHE_SIZE` if memory-constrained
- Verify `chain_prediction_cache` is cleared on bomb spawn

### Overly Aggressive Suicide
- Lower `personality_weights.aggression` (800 → 600)
- Increase `MIN_ESCAPE_BUFFER` (1.5 → 2.0)
- Raise `risk_tolerance` threshold in `can_place_bomb_safely`

---

## Migration Notes

### Pre-Upgrade Behavior
- Discrete danger zones with snapshot timing
- 10 action types (missing flank/kite/explore/control)
- Static opponent tracking (no roles or power gaps)
- Tile-based jerky movement

### Post-Upgrade Behavior
- Continuous heatmap with per-tick countdown
- 16 action types with guaranteed fallback
- Adaptive profiling with role-based counter-play
- Smooth steering with replanning triggers

**Compatibility:** Fully backward-compatible. Old `get_danger_at_tile()` API preserved, new methods additive.

---

## Future Enhancements

1. **Machine Learning Integration:** Replace utility scoring with trained Q-network
2. **Multi-Agent Coordination:** Team-based trap setups for 2v2 modes
3. **Map-Specific Strategies:** Choke-point control on narrow maps
4. **Dynamic Difficulty Scaling:** Adjust `personality_weights` based on player skill

---

## Credits

**Implementation:** GitHub Copilot (Claude Sonnet 4.5)  
**Architecture:** 7-phase systematic overhaul  
**Reference:** SBomberman project for authoritative multiplayer patterns  
**Testing:** Godot 4.5 with server-side AI validation

---

**End of AI Upgrade Guide**

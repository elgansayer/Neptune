# Competitive Multiplayer AI Implementation Plan

**Status:** Draft for classic bomb + NavigationServer2D baseline – dash & new bomb archetypes intentionally deferred.

## 1. Goals & Constraints
- **Authoritative server**: All bot decisions run inside `server/game_instance.gd`, pushing inputs to `shared/entities/server_player.gd` just like human players (`set_input`, `request_action_press`, `request_action_release`, `request_bomb_placement`).
- **Map-driven grids**: Tile size, walkability, and spawn data always come from `GameConfig` + map metadata (see `docs/MAP_SYSTEM.md`). No hardcoded tile sizes.
- **Fast, competitive feel**: Decisions must respect latency policies in `docs/LAG_MITIGATION.md` (60 Hz sim / 20 Hz sync) and the smooth/authoritative pillars from `prompt.md` + `PLAN.md`.
- **Behavior stack**: Behavior Trees enhanced with optional utility scoring per user request. Stick with the classic bomb implementation in `shared/entities/server_bomb.gd`; new bomb types will plug in later.
- **Plugin priority**: NavigationServer2D pathfinding → optional grid path add-ons → behavior authoring → telemetry/analytics.

## 2. Module Topology
```
shared/
  ai/
    perception/
      grid_sampler.gd          # Tile sampling + occupancy cache
      hazard_predictor.gd      # Bomb danger + escape windows (wraps DangerMapper)
      opponent_tracker.gd      # Estimates intent, last-seen, aggression markers
    behavior_tree/
      bt_runner.gd             # Tick scheduler + blackboard
      nodes/
        selector.gd
        sequence.gd
        utility_selector.gd    # Selector with scoring hook
        leaf_move_to.gd
        leaf_place_bomb.gd
        leaf_collect_powerup.gd
        leaf_wait_ambush.gd
    config/
      personalities.gd         # Personality weights referencing docs/AI_PERSONALITIES_REFERENCE.md
      tuning.gd                # Decision cadences, escape margins, bomb heuristics
server/
  ai/
    bot_manager.gd             # Spawns bots, wires them to GameInstance
    bot_controller.gd          # Orchestrates perception → behavior tree per bot and writes `input_data`
    telemetry/
      ai_metrics_logger.gd     # Optional plugin-ready telemetry hooks
```
- **Reuse**: Existing `shared/ai/danger_mapper.gd`, `utility_scorer.gd`, `bomb_planner.gd`, and `player_log_manager.gd` remain reusable helpers (see `docs/IMPROVED_AI_SYSTEM.md`). New perception nodes wrap them for BT consumption.

## 3. Server Integration Flow
1. `server/ai/bot_manager.gd` registers with `GameInstance` during `_ready()`.
2. When a bot is spawned, `bot_manager` instantiates `bot_controller.gd`, giving it:
   - References to `GameInstance`, `ServerPlayer`, `GameConfig`, `DangerMapper`, `BombPlanner`.
   - Personality config (enum + JSON) loaded from `shared/ai/config/personalities.gd`.
3. Each physics frame (`_physics_process` at 60 Hz), `bot_controller`:
   - Updates perception caches (grid occupancy, bomb hazards, opponent states).
   - Ticks the behavior tree runner (default 10 Hz, overridable per personality) with Blackboard values (`current_tile`, `danger_window`, `has_bomb`, etc.).
   - Produces an action struct `{move_vector, request_bomb, request_action}`.
   - Translates to authoritative inputs by calling `ServerPlayer.set_input`, `request_action_press/release`, `request_bomb_placement` (bomb placement uses existing server validation).
4. `GameInstance.handle_player_input` continues to run for humans; bots bypass RPC by writing directly each tick, but still respect `ServerPlayer` public APIs for parity.

## 4. Perception Stack
- **Grid Sampler (`grid_sampler.gd`)**
  - Builds/updates a `NavigationRegion2D` via NavigationServer2D using map collision data. Rebuild cadence driven by map changes (soft block destroyed, bombs placed).
  - Provides helpers `world_to_tile`, `tile_to_world_center`, and cached walkability checks referencing `GameConfig.TILE_SIZE`.
- **Hazard Predictor (`hazard_predictor.gd`)**
  - Wraps `DangerMapper` to expose `get_time_to_safety(tile)`, `is_tile_enterable(tile, buffer_ms)`.
  - Simulates the single classic bomb path only; future bomb types inject new behaviors via strategy objects.
- **Opponent Tracker (`opponent_tracker.gd`)**
  - Observes other `ServerPlayer` nodes and stores last-known tile, velocity vector, power-up possession.
  - Provides heuristics: `nearest_aggressor_distance`, `opponent_in_trap_window`, `powerup_race_targets`.
- **Blackboard Schema**
  - `blackboard.current_tile` (Vector2i)
  - `blackboard.path` (Array<Vector2>) – reused between ticks until invalidated
  - `blackboard.danger_level` (float seconds until blast)
  - `blackboard.personality` (struct of weights)
  - `blackboard.goal_tile` / `goal_type`

## 5. Behavior Tree Runtime
- Implemented in `shared/ai/behavior_tree/bt_runner.gd`:
  - Supports classic `Selector`, `Sequence`, `Decorator`, plus `UtilitySelector` nodes that call into `shared/ai/utility_scorer.gd` for weight calculation (scores already documented in `docs/AI_QUICK_REFERENCE.md`).
  - Leaf nodes translate decisions into Blackboard updates (`set_goal(tile, intent)`) or immediate actions (e.g., `leaf_place_bomb` verifying `BombPlanner.can_place_bomb_safely`).
- **Default Tree Skeleton**:
```
Root
 └─ UtilitySelector (EmergencyEscape, Combat, Objectives, Patrol)
     • EmergencyEscapeSequence
         - CheckDangerNode (< personality.escape_threshold)
         - PlanEscapeLeaf (hazard_predictor.find_escape())
     • CombatSequence
         - OpponentVisible?
         - PlanTrapOrChase
         - ExecuteMove/Bomb Leaf
     • ObjectiveSequence
         - PowerupAvailable?
         - MoveToPowerupLeaf
     • PatrolSequence
         - Explore/RandomWalk
```
- Personalities (Balanced, Aggressive, etc.) supply tuning for utility weights, decision cadence, and thresholds exactly as outlined in `docs/AI_PERSONALITIES_REFERENCE.md`.

## 6. Plugin Strategy
1. **NavigationServer2D baseline (required now)**
   - All pathfinding uses Godot’s built-in navigation regions per map. Keeps dependencies light and stable.
2. **Optional grid pathfinding addons (future)**
   - Candidates: `godot-gdpath` or other A* grid helpers for hazard-aware heuristics, caching, and visualization. Integrate only if NavigationServer2D proves insufficient for hazard prediction around bombs.
3. **Behavior authoring tools (later)**
   - Evaluate addons like `BehaviorTreePlugin` once baseline is stable; their editors could visualize tree states but must remain optional.
4. **Telemetry / analytics plugins**
   - Continue to use `PlayerLogManager`; plan for additional exporters (CSV/JSON) to feed ML or balancing dashboards.

## 7. Testing Strategy
- **Unit-style tests (`shared/tests/ai/`)**
  - `test_danger_predictor.gd`: ensures hazard predictions match bomb fuse timings (3 s classic fuse, 0.5 s buffer).
  - `test_bt_transitions.gd`: loads mock Blackboard states to validate node ordering and emergency overrides.
- **Integration scenes**
  - `server/tests/ai_playground.tscn`: headless map with soft blocks to run bots vs dummy targets.
  - Scripts to simulate bombs, check for suicides, confirm kicking/Power Glove interactions still work when bots trigger them through `ServerPlayer` APIs.
- **Telemetry validation**
  - Enable `PlayerLogManager` for bots to ensure logging pipeline can differentiate AI vs human data and remain usable for imitation learning.

## 8. Roadmap & Dependencies
1. **Foundation (Sprint 1)**
   - Implement new AI directories and scaffolding files.
   - Port/reuse `DangerMapper`, `UtilityScorer`, `BombPlanner`, `PlayerLogManager` inside the new behavior-tree runner.
   - Wire `bot_manager` into `GameInstance` with manual toggles in project settings.
2. **Behavior authoring (Sprint 2)**
   - Build out behavior tree nodes, load personality configs, and finalize Blackboard schema.
   - Ensure emergency escape path is bulletproof (never worse than current Improved AI safety). 
3. **Perception polish (Sprint 3)**
   - Add opponent heuristics, power-up targeting, and hazard-aware NavigationServer2D path smoothing.
4. **Telemetry & tooling (Sprint 4)**
   - Hook metrics logger, optional behavior editor, and consider grid-path plugin if profiling reveals hotspots.
5. **Future bomb variants**
   - Once new bomb archetypes are ready, add strategy interfaces so hazard predictor & BT leaves can swap explosion models without reworking the base architecture.

## 9. Open Questions / Next Inputs Needed
- Confirm desired spawn counts and matchmaking hooks for automatic bot fill in lobbies.
- Decide when to enable optional plugins (grid pathfinding, behavior editors) so we can budget time for integration and QA.
- Define acceptance tests for “competitive-ready” bots (e.g., minimum survival time, kill/death ratio vs baseline personalities).

This plan gives us an authoritative, extensible AI stack aligned with existing documentation while leaving clear seams for future dash abilities and new bomb types.

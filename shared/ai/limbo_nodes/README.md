# LimboAI Custom Nodes for Neptune-Bomberman

This directory contains custom Behavior Tree nodes for use with LimboAI in the Neptune-Bomberman project.

## Directory Structure

```
limbo_nodes/
├── conditions/          # BTCondition nodes (decision points)
│   ├── bt_is_in_danger.gd
│   ├── bt_is_cell_walkable.gd
│   ├── bt_has_powerup.gd
│   └── bt_has_client_input.gd
│
├── actions/            # BTAction nodes (do things)
│   ├── bt_move_to_cell.gd
│   ├── bt_place_bomb.gd
│   ├── bt_update_input_from_buffer.gd
│   ├── bt_process_power_glove.gd
│   └── bt_find_escape_route.gd
│
└── README.md           # This file
```

## Node Categories

### Conditions (Return SUCCESS or FAILURE)

Condition nodes evaluate game state and return SUCCESS if the condition is met, FAILURE otherwise.

#### bt_is_in_danger.gd
Checks if the entity is currently in explosion danger.

**Exports**:
- `danger_buffer: float` - Safety margin in seconds
- `check_immediate: bool` - Check only immediate danger

**Blackboard Reads**:
- `player` - The entity to check
- `hazard_predictor` - HazardPredictor reference

**Blackboard Writes**:
- `in_danger: bool` - Current danger state
- `danger_tile: Vector2i` - Tile with danger

**Usage**: Start of escape sequences

#### bt_is_cell_walkable.gd
Checks if a specific cell is walkable (not blocked by walls/obstacles).

**Exports**:
- `cell_var: StringName` - Blackboard variable name for the cell to check

**Blackboard Reads**:
- `grid_sampler` - GridSampler reference
- `[cell_var]` - The cell position to check

**Usage**: Path validation, movement planning

#### bt_has_powerup.gd
Checks if the player has a specific powerup ability.

**Exports**:
- `powerup_type: PowerupType` - Which powerup to check for

**Powerup Types**:
- `BOMB_KICKER` - Can kick bombs
- `POWER_GLOVE` - Can pick up and throw bombs
- `SPEED_BOOST` - Has speed increase
- `BOMB_INCREASE` - Has max bombs increased
- `RANGE_INCREASE` - Has bomb range increased

**Blackboard Reads**:
- `player` - Player to check

**Usage**: Conditional behavior based on abilities

#### bt_has_client_input.gd
Checks if there is client input available (for player-controlled entities).

**Exports**:
- `input_action: String` - Specific input to check
- `check_any: bool` - Check for any input instead

**Blackboard Reads**:
- `input_buffer` - InputBuffer reference (if check_any)
- `[input_action]` - Specific input value (if not check_any)

**Usage**: Player BT input processing

---

### Actions (Perform operations, return SUCCESS/FAILURE/RUNNING)

Action nodes perform operations and can run over multiple frames (RUNNING state).

#### bt_move_to_cell.gd
Moves the entity toward a target cell.

**Exports**:
- `cell_var: StringName` - Blackboard variable with target cell
- `reach_threshold: float` - Distance to consider "reached" (in tiles)
- `clear_on_success: bool` - Clear target_cell when reached

**Blackboard Reads**:
- `player` - Entity to move
- `[cell_var]` - Target cell position

**Blackboard Writes**:
- `[cell_var]` - Cleared on success (if clear_on_success)

**Returns**:
- `RUNNING` - Still moving
- `SUCCESS` - Reached destination
- `FAILURE` - Invalid target or player

**Usage**: All movement behaviors

#### bt_place_bomb.gd
Places a bomb at the player's current position.

**Exports**:
- `check_capacity: bool` - Verify player can place bomb
- `check_existing: bool` - Verify no bomb already at position

**Blackboard Reads**:
- `player` - Player to place bomb
- `game_instance` - GameInstance reference

**Blackboard Writes**:
- `last_bomb_placed_at: Vector2i` - Position of last bomb
- `last_bomb_placed_time: float` - Timestamp

**Returns**:
- `SUCCESS` - Bomb placed
- `FAILURE` - Cannot place (at capacity or bomb exists)

**Usage**: Attack and trap behaviors

#### bt_update_input_from_buffer.gd
Reads the latest input from the input buffer and stores in blackboard.

**Exports**:
- `peek_only: bool` - Don't consume input (just read it)

**Blackboard Reads**:
- `input_buffer` - InputBuffer reference
- `player` - Player to set input on

**Blackboard Writes**:
- `input_x: float` - Movement X
- `input_y: float` - Movement Y
- `action_pressed: bool` - Action button pressed
- `action_released: bool` - Action button released
- `place_bomb: bool` - Bomb placement requested
- `has_input: bool` - Whether any input exists

**Returns**:
- `SUCCESS` - Always (even if no input)
- `FAILURE` - Missing required references

**Usage**: First node in player controller BT

#### bt_process_power_glove.gd
Handles Power Glove logic (throw, pickup, place).

**Exports**:
- `consume_input_on_action: bool` - Consume input after processing

**Blackboard Reads**:
- `player` - Player reference
- `game_instance` - GameInstance reference
- `action_pressed: bool` - Action button state

**Blackboard Writes**:
- `last_action: String` - Last action performed ("throw_bomb", "pickup_bomb", "place_bomb", "none")

**Returns**:
- `SUCCESS` - Action processed (or no action needed)
- `FAILURE` - Missing required references

**Priority**:
1. Throw (if carrying)
2. Pickup (if bomb underfoot)
3. Place (if can place)

**Usage**: Player controller with Power Glove

#### bt_find_escape_route.gd
Finds a safe escape route from danger using pathfinding.

**Exports**:
- `escape_radius: int` - How far to search for safety
- `target_cell_var: StringName` - Where to store the result

**Blackboard Reads**:
- `player` - Entity to find route for
- `game_instance` - GameInstance reference
- `ai_manager` - AIManager with pathfinder

**Blackboard Writes**:
- `[target_cell_var]` - Escape destination
- `escape_route_found: bool` - Whether route was found

**Returns**:
- `SUCCESS` - Safe route found
- `FAILURE` - No escape route available

**Usage**: Escape behaviors

---

## Blackboard Conventions

### Common Variables

These variables should be available in most BTs:

**Entity References**:
- `player: ServerPlayer` - The entity this BT controls
- `game_instance: GameInstance` - The game world
- `ai_manager: AIManager` - Centralized AI services

**Perception Systems**:
- `grid_sampler: GridSampler` - Map queries
- `hazard_predictor: HazardPredictor` - Danger detection
- `opponent_tracker: OpponentTracker` - Player tracking
- `bomb_planner: BombPlanner` - Tactical planning

**State Variables**:
- `current_tile: Vector2i` - Entity's tile position
- `target_cell: Vector2i` - Movement destination
- `in_danger: bool` - Danger state
- `has_input: bool` - Input availability (players only)

**Input Variables** (Player BTs only):
- `input_buffer: InputBuffer` - Buffered client inputs
- `input_x: float` - Movement X (-1 to 1)
- `input_y: float` - Movement Y (-1 to 1)
- `action_pressed: bool` - Action button state
- `place_bomb: bool` - Bomb placement request

### Variable Naming Conventions

- **Entity refs**: `player`, `bomb`, `powerup`
- **System refs**: `game_instance`, `ai_manager`
- **Positions**: Use `Vector2i` for tile positions, `Vector2` for world positions
- **Booleans**: Prefix with `is_`, `has_`, `can_`
- **Timestamps**: Suffix with `_time`

---

## Creating New Custom Nodes

### Condition Template

```gdscript
@tool
extends BTCondition
class_name BTYourCondition

## Brief description of what this condition checks

@export var some_parameter: float = 1.0  ## Parameter description

func _generate_name() -> String:
    return "YourCondition(%s)" % some_parameter

func _tick(delta: float) -> int:
    # Get required blackboard variables
    var entity = blackboard.get_var("player")
    
    if not entity:
        push_warning("[BTYourCondition] Missing required variable")
        return FAILURE
    
    # Evaluate condition
    if _your_condition_check(entity):
        return SUCCESS
    else:
        return FAILURE

func _your_condition_check(entity) -> bool:
    # Implement your logic here
    return false
```

### Action Template

```gdscript
@tool
extends BTAction
class_name BTYourAction

## Brief description of what this action does

@export var some_parameter: float = 1.0  ## Parameter description

func _generate_name() -> String:
    return "YourAction"

func _tick(delta: float) -> int:
    # Get required blackboard variables
    var entity = blackboard.get_var("player")
    
    if not entity:
        push_warning("[BTYourAction] Missing required variable")
        return FAILURE
    
    # Perform action
    var result = _perform_action(entity, delta)
    
    # Store results in blackboard if needed
    blackboard.set_var("result", result)
    
    return SUCCESS  # or FAILURE or RUNNING

func _perform_action(entity, delta) -> void:
    # Implement your logic here
    pass
```

---

## Testing Custom Nodes

### Unit Test Example

```gdscript
extends GutTest

func test_is_in_danger_detects_bomb():
    # Setup
    var game = autoqfree(GameInstance.new())
    add_child(game)
    
    var player = autoqfree(ServerPlayer.new())
    game.add_child(player)
    
    # Place bomb near player
    var bomb = autoqfree(ServerBomb.new())
    bomb.position = player.position + Vector2(64, 0)
    game.bombs["test"] = bomb
    
    # Create condition node
    var condition = BTIsInDanger.new()
    
    # Setup blackboard
    var blackboard = Blackboard.new()
    blackboard.set_var("player", player)
    blackboard.set_var("hazard_predictor", game.hazard_predictor)
    condition.blackboard = blackboard
    
    # Test
    var result = condition._tick(0.1)
    
    # Assert
    assert_eq(result, BTTask.SUCCESS, "Should detect danger from nearby bomb")
```

---

## Performance Considerations

### Expensive Operations

Some nodes may perform expensive operations:

- **BTFindEscapeRoute**: Uses pathfinding (expensive)
- **BTIsInDanger**: Queries threat matrix (moderate)
- **BTIsCellWalkable**: Queries map grid (cheap)

### Optimization Tips

1. **Cache Results**: Store results in blackboard when appropriate
2. **Reduce Tick Rate**: Tick distant entities less frequently
3. **Early Returns**: Check simple conditions before expensive ones
4. **Batch Operations**: Update perception systems once per frame, not per entity

---

## Integration with Existing Systems

### GridSampler
Used for map queries (walkability, obstacles).

**Location**: `shared/ai/perception/grid_sampler.gd`

### HazardPredictor
Used for danger detection and explosion prediction.

**Location**: `shared/ai/perception/hazard_predictor.gd`

### AIManager
Centralized AI services (pathfinding, threat matrix).

**Location**: `shared/ai/ai_manager.gd`

### InputBuffer
Buffers client inputs for player entities.

**Location**: `shared/entities/input_buffer.gd`

---

## Documentation

For complete documentation on refactoring to LimboAI:

- **Installation**: `docs/LIMBOAI_INSTALLATION.md`
- **Refactoring Guide**: `docs/LIMBOAI_REFACTOR_GUIDE.md`
- **BT Examples**: `docs/LIMBOAI_BT_EXAMPLES.md`
- **Quick Start**: `docs/LIMBOAI_QUICKSTART.md`

---

## Contributing

When adding new custom nodes:

1. Follow the template structure
2. Add `@tool` annotation for editor use
3. Implement `_generate_name()` for readable names
4. Document exports and blackboard variables
5. Add error checking with `push_warning()`
6. Update this README with the new node
7. Create unit tests

---

**Questions?** See the full documentation in `docs/` directory.

# Behavior Tree Integration Guide

## New AI Behaviors Added

Three new BT nodes have been created to enhance competitive AI:

1. **bt_set_trap.gd** - Strategic trap-setting behavior
2. **bt_predict_opponent.gd** - Opponent movement prediction and interception
3. **bt_evade_rubber_bomb.gd** - Specialized rubber bomb evasion

## Integration into bot_default.tres

Since .tres files are binary-encoded Godot resources, you need to edit them in the Godot Editor. Follow these steps:

### Step 1: Open Godot Editor
```bash
cd /home/elgan/bomberman
godot --editor
```

### Step 2: Open the Behavior Tree
1. Navigate to `res://ai/trees/bot_default.tres` in the FileSystem
2. Double-click to open in the LimboAI behavior tree editor

### Step 3: Enable Attack Sequence
The attack sequence is currently disabled. Enable it:
1. Find the "Chase + Attack Sequence" node
2. In the Inspector, ensure `_enabled` checkbox is **checked**

### Step 4: Add Rubber Bomb Evasion to Escape Sequence

**Current Escape Sequence:**
```
BTSequence_escape
├─ BTCondition_escape_check (Is In Danger)
├─ BTAction_escape_find (Find Escape Route)
└─ BTAction_escape_move (Move To Safe Tile)
```

**Enhanced Escape Sequence:**
```
BTSelector_escape (NEW - try rubber bomb evasion first)
├─ BTSequence_rubber_bomb_escape (NEW)
│  ├─ BTEvadeRubberBomb → evade_cell
│  └─ BTMoveToCell (cell_var: evade_cell)
└─ BTSequence_normal_escape (existing escape logic)
   ├─ BTCondition_escape_check
   ├─ BTAction_escape_find
   └─ BTAction_escape_move
```

**How to add:**
1. Right-click on root selector
2. Find the Escape Sequence node
3. Replace it with a Selector containing two sequences:
   - First: Rubber bomb evasion (higher priority)
   - Second: Normal escape (fallback)

### Step 5: Enhance Attack Sequence with Prediction and Trapping

**Current Attack Sequence:**
```
BTSequence_attack
├─ BTCondition_has_opponent
├─ BTAction_find_opponent
├─ BTAction_chase_move
├─ BTAction_attack_place
├─ BTAction_attack_plan_retreat
└─ BTAction_attack_move
```

**Enhanced Attack Sequence:**
```
BTSequence_attack_enhanced
├─ BTCondition_has_opponent (existing, max_distance: 10)
├─ BTSelector_attack_strategy (NEW)
│  ├─ BTSequence_trap_strategy (Try trap first - for Aggressive/Strategic/Trapper)
│  │  ├─ BTSetTrap → trap_target_cell
│  │  ├─ BTMoveToCell (cell_var: trap_target_cell)
│  │  └─ BTPlaceBomb (require_at_target: true)
│  └─ BTSequence_chase_strategy (Fallback to direct chase)
│     ├─ BTPredictOpponent → intercept_cell
│     ├─ BTMoveToCell (cell_var: intercept_cell)
│     └─ BTPlaceBomb
├─ BTAction_attack_plan_retreat (existing)
└─ BTAction_attack_move (existing)
```

**How to add:**
1. Create a new Selector node under the attack sequence
2. Add two child sequences:
   - Trap strategy (checks if trap is possible, sets it up)
   - Chase strategy (direct pursuit with prediction)

### Step 6: Add New External Resources

At the top of bot_default.tres, add these external resources:

```gdscript
[ext_resource type="Script" uid="uid://..." path="res://ai/tasks/actions/bt_set_trap.gd" id="10_trap"]
[ext_resource type="Script" uid="uid://..." path="res://ai/tasks/actions/bt_predict_opponent.gd" id="11_predict"]
[ext_resource type="Script" uid="uid://..." path="res://ai/tasks/actions/bt_evade_rubber_bomb.gd" id="12_evade"]
```

### Step 7: Configure Personality-Based Behavior

The new nodes use personality parameters from the blackboard:
- `trap_aggression` - How likely to attempt traps (0.0-1.0)
- `prediction_lookahead` - How far ahead to predict (1-5 tiles)
- `corner_preference` - How much to prioritize cornering (0.0-1.0)

These are automatically loaded from `bot_manager.gd` based on personality.

## Alternative: Script-Based Tree Generation

If manual editing is too complex, here's a GDScript to generate the enhanced tree:

```gdscript
# Run this in Godot's script editor or as a tool script

extends EditorScript

func _run():
	var tree = BehaviorTree.new()
	tree.description = "Enhanced competitive AI with trapping, prediction, and rubber bomb evasion"
	
	# Root loop
	var root_loop = BTRepeatUntilFailure.new()
	root_loop.custom_name = "Continuous Loop"
	
	# Main selector
	var root_selector = BTSelector.new()
	
	# 1. Enhanced Escape (with rubber bomb evasion)
	var escape_selector = BTSelector.new()
	escape_selector.custom_name = "Escape Strategy Selector"
	
	# ... (rest of tree construction)
	
	ResourceSaver.save(tree, "res://ai/trees/bot_competitive.tres")
	print("Generated enhanced behavior tree: bot_competitive.tres")
```

## Testing

After integration, test with:
```bash
timeout 300s bash -c 'clear && echo "time" > server.log && clear && ./bomberman both; tail -f server.log'
```

Watch for:
- Bots attempting to trap opponents
- Predictive interception during chase
- Perpendicular movement when evading kicked bombs
- Aggressive personalities using traps more frequently

## Personality Recommendations

- **AGGRESSIVE**: trap_aggression=0.9, corner_preference=0.8
- **STRATEGIC**: trap_aggression=0.7, prediction_lookahead=5
- **TRAPPER**: trap_aggression=1.0, ambush_patience=10.0
- **BALANCED**: trap_aggression=0.5, prediction_lookahead=3

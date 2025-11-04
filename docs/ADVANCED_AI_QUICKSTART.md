# Advanced AI Quickstart Guide

## Overview

The Bomberman AI system now includes **11 personalities**, including two advanced personalities powered by machine learning algorithms:

- **LEARNED** (Type 9): Uses Q-Learning (Reinforcement Learning) to improve over time
- **PERFECT** (Type 10): Uses MCTS (Monte Carlo Tree Search) for expert-level planning

## Quick Usage

### Spawning Advanced AI Bots

**In-Game (via RPC)**:
```gdscript
# Spawn a LEARNED bot (Q-Learning)
rpc_id(1, "request_spawn_bot", 9)  # Type 9 = LEARNED

# Spawn a PERFECT bot (MCTS)
rpc_id(1, "request_spawn_bot", 10)  # Type 10 = PERFECT
```

**Server Code**:
```gdscript
# In GameInstance or MainServer
var AIPersonality = preload("res://shared/ai/ai_personalities.gd")

# Spawn LEARNED bot
game_instance.add_ai_bot(AIPersonality.Type.LEARNED)

# Spawn PERFECT bot
game_instance.add_ai_bot(AIPersonality.Type.PERFECT)
```

---

## LEARNED Personality (Q-Learning)

### Characteristics

- **Algorithm**: Q-Learning (Temporal Difference Reinforcement Learning)
- **Learning**: Improves over 50-100 matches
- **Decision Speed**: Fast (~1ms)
- **Reaction Time**: 30ms
- **Playstyle**: Initially random, becomes strategic

### How It Works

The bot learns by:
1. **Exploring** the environment (10% random actions)
2. **Exploiting** known good moves (90% best actions)
3. **Updating** Q-values based on rewards:
   - +500 for kills
   - +50 for block destruction
   - -1000 for death
   - +30 for escaping danger

### Training the LEARNED Bot

The bot automatically saves its Q-table to `user://q_table.json` after each match. To train:

1. **Spawn LEARNED bot**: Add to matches repeatedly
2. **Let it learn**: Play 50-100 matches with it
3. **Observe improvement**: Check stats with `controller.get_learning_stats()`
4. **Persistent learning**: Q-table loads automatically on next spawn

**Reset Learning**:
```bash
# Delete saved Q-table to start fresh
rm ~/.local/share/godot/app_userdata/Bomberman\ Server/q_table.json
```

### Q-Learning Stats

```gdscript
# Get learning statistics
var stats = bot_controller.get_learning_stats()
print("States learned: ", stats.states_learned)
print("Episodes completed: ", stats.episodes)
print("Average reward: ", stats.avg_reward)
```

### Expected Behavior

**Early Matches (1-20)**:
- Random movement
- Poor bomb placement
- Dies frequently
- Explores map

**Mid Training (20-50)**:
- Avoids danger
- Chases opponents
- Destroys blocks strategically
- Still makes mistakes

**Late Training (50+)**:
- Strong tactical play
- Map-specific strategies
- Good trap setup
- Competitive with human players

---

## PERFECT Personality (MCTS)

### Characteristics

- **Algorithm**: Monte Carlo Tree Search with UCB1
- **Learning**: No training required
- **Decision Speed**: Slower (~50ms per decision)
- **Reaction Time**: 50ms
- **Playstyle**: Highly tactical, calculating, defensive

### How It Works

The bot plans ahead by:
1. **Building a tree** of possible moves (100 simulations)
2. **Selecting** promising branches using UCB1 formula
3. **Simulating** 10 moves ahead to predict outcomes
4. **Choosing** the move with highest expected reward

### Planning Depth

- **Simulations per decision**: 100
- **Time budget**: 50ms
- **Lookahead depth**: 10 moves
- **Discount factor**: 0.95 (future rewards decay)

### Expected Behavior

**Always**:
- Plans multiple moves ahead
- Excellent danger avoidance
- Strong positional play
- Controls map center and choke points

**Strengths**:
- Multi-bomb trap escapes
- Counter-trapping opponents
- Resource denial (blocking power-ups)
- Endgame superiority

**Weaknesses**:
- Slightly slower reactions (50ms)
- Assumes random opponent behavior
- CPU intensive (limit to 1-2 per match)

---

## Performance Comparison

| Personality | Decision Time | Training Needed | Skill Level | Best For |
|-------------|--------------|-----------------|-------------|----------|
| **Balanced** | ~1ms | None | Medium | Standard gameplay |
| **Aggressive** | ~1ms | None | Medium | Rushdown tactics |
| **Strategic** | ~2ms | None | High | Trap-focused play |
| **LEARNED** | ~1ms | 50+ matches | Low → Very High | Long-term learning |
| **PERFECT** | ~50ms | None | Very High | Expert opponents |

---

## Recommended Bot Combinations

### Training Match (Help LEARNED Bot Learn)
```gdscript
add_ai_bot(AIPersonality.Type.LEARNED)   # Learning bot
add_ai_bot(AIPersonality.Type.BALANCED)  # Consistent opponent
add_ai_bot(AIPersonality.Type.TIMID)     # Easy target
```

### Challenging Match
```gdscript
add_ai_bot(AIPersonality.Type.PERFECT)    # Expert planner
add_ai_bot(AIPersonality.Type.STRATEGIC)  # Trap specialist
add_ai_bot(AIPersonality.Type.KAMIKAZE)   # Unpredictable aggressor
```

### Mixed Difficulty
```gdscript
add_ai_bot(AIPersonality.Type.PERFECT)    # Hard
add_ai_bot(AIPersonality.Type.LEARNED)    # Medium (if trained)
add_ai_bot(AIPersonality.Type.AGGRESSIVE) # Easy-Medium
```

---

## Advanced Configuration

### Tuning Q-Learning

Edit `shared/ai/ai_q_learning.gd`:

```gdscript
# Learning rate (how much to update Q-values)
var learning_rate: float = 0.1  # Default: 0.1 (conservative)

# Discount factor (how much to value future rewards)
var discount_factor: float = 0.95  # Default: 0.95 (far-sighted)

# Exploration rate (chance of random action)
var epsilon: float = 0.1  # Default: 0.1 (10% exploration)
```

**Effects**:
- Higher learning_rate → Faster learning, less stable
- Higher discount_factor → More long-term planning
- Higher epsilon → More exploration, slower convergence

### Tuning MCTS

Edit `shared/ai/ai_mcts.gd`:

```gdscript
# Max simulations per decision
var max_iterations: int = 100  # Default: 100

# Time budget per decision (ms)
var time_budget_ms: float = 50.0  # Default: 50ms

# Exploration constant (UCB1)
var exploration_constant: float = 1.41  # Default: √2

# Simulation depth
var max_depth: int = 10  # Default: 10 moves
```

**Effects**:
- Higher max_iterations → Better decisions, slower
- Higher time_budget_ms → More accurate, higher CPU
- Higher exploration_constant → More exploratory, less greedy
- Higher max_depth → Longer planning, more accurate

---

## Troubleshooting

### LEARNED Bot Not Learning

**Symptoms**: Bot doesn't improve after many matches

**Solutions**:
1. Check Q-table is saving: `ls ~/.local/share/godot/app_userdata/Bomberman\ Server/`
2. Verify training hooks are called: Add prints to `on_player_death()`, `on_player_kill()`
3. Reset Q-table and retrain from scratch
4. Increase exploration: Set `epsilon = 0.2` in `ai_q_learning.gd`

### PERFECT Bot Too Slow

**Symptoms**: Game lags when PERFECT bot is active

**Solutions**:
1. Reduce simulations: `max_iterations = 50` in `ai_mcts.gd`
2. Reduce time budget: `time_budget_ms = 30.0`
3. Limit PERFECT bots to 1 per match
4. Use PERFECT only in important matches

### Q-Learning Converges to Suboptimal Strategy

**Symptoms**: LEARNED bot develops bad habits

**Solutions**:
1. Adjust reward function in `ai_q_learning.gd`
2. Increase exploration: `epsilon = 0.15`
3. Train against varied opponents (not just one personality)
4. Reset and retrain with better reward weights

---

## Files Reference

| File | Purpose |
|------|---------|
| `shared/ai/ai_q_learning.gd` | Q-Learning implementation |
| `shared/ai/ai_mcts.gd` | MCTS implementation |
| `shared/ai/ai_bot_controller.gd` | Integration logic |
| `shared/ai/ai_personalities.gd` | Personality configurations |
| `AI_Bot_Implementation_Plan.md` | Technical documentation |
| `docs/AI_PERSONALITIES_REFERENCE.md` | All personalities guide |

---

## Next Steps

1. **Test LEARNED bot**: Spawn and observe learning over 10 matches
2. **Test PERFECT bot**: Spawn and observe tactical play
3. **Compare**: Run matches with LEARNED vs PERFECT vs human players
4. **Tune**: Adjust parameters based on observed behavior
5. **Train**: Run extended training sessions for LEARNED bot (100+ matches)

---

## Future Enhancements

- **Neural Q-Learning**: Replace Q-table with neural network (Deep Q-Learning)
- **AlphaZero-style MCTS**: Use neural network for value estimation
- **Hybrid System**: Use Q-values to guide MCTS simulations
- **Opponent Modeling**: Track and predict opponent behavior patterns
- **Transfer Learning**: Train on one map, transfer to others

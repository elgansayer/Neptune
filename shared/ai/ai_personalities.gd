extends Node
class_name AIPersonality

# AI Bot Personality System
# Defines different playstyles through utility weight tuning

enum Type {
	BALANCED,    # Well-rounded, standard difficulty
	AGGRESSIVE,  # High risk, high reward - loves trapping opponents
	TIMID,       # Safety first, avoids confrontation
	GREEDY,      # Power-up focused, strategic collector
	CHAOS,       # Unpredictable, bombs everywhere
	DEFENSIVE,   # Wall hugger, corner camper, extremely cautious
	KAMIKAZE,    # Suicide bomber, trades kills, no fear
	STRATEGIC,   # Chess player, plans ahead, calculates optimal moves
	TRAPPER,     # Ambush specialist, sets elaborate traps
	LEARNED,     # Q-Learning AI, learns from experience
	PERFECT      # MCTS AI, simulates future moves for optimal play
}

# Utility scoring weights for different personalities
# These values tune the bot's decision-making priorities

static func get_weights(personality_type: Type) -> Dictionary:
	match personality_type:
		Type.BALANCED:
			return {
				"safety": 1000.0,
				"danger_penalty": -10000.0,
				"powerup": 500.0,
				"aggression": 400.0,  # Increased
				"exploration": 150.0,  # Increased
				"escape_route": 50.0,
				"proximity_penalty": -150.0,  # Less penalty
				"idle_penalty": -50.0,
				"trap_bonus": 500.0,  # Increased
				"bomb_frequency": 0.4,  # Increased
				"reaction_delay": 0.05,  # 50ms - faster
				"pathfinding_frequency": 0.3  # Faster updates
			}
		
		Type.AGGRESSIVE:
			return {
				"safety": 700.0,  # Increased slightly
				"danger_penalty": -8000.0,  # Less risky
				"powerup": 300.0,
				"aggression": 1000.0,  # Much higher
				"exploration": 200.0,  # Increased
				"escape_route": 30.0,
				"proximity_penalty": 0.0,  # Loves being close
				"idle_penalty": -150.0,
				"trap_bonus": 1200.0,  # Much higher
				"bomb_frequency": 0.7,  # More bombs
				"reaction_delay": 0.02,  # 20ms - very fast
				"pathfinding_frequency": 0.2  # Faster
			}
		
		Type.TIMID:
			return {
				"safety": 2000.0,
				"danger_penalty": -15000.0,
				"powerup": 500.0,  # Increased
				"aggression": 100.0,  # Increased
				"exploration": 250.0,  # Increased
				"escape_route": 150.0,
				"proximity_penalty": -500.0,
				"idle_penalty": -30.0,
				"trap_bonus": 150.0,  # Increased
				"bomb_frequency": 0.2,  # Increased
				"reaction_delay": 0.08,  # Faster
				"pathfinding_frequency": 0.4  # Faster
			}
		
		Type.GREEDY:
			return {
				"safety": 800.0,
				"danger_penalty": -9000.0,
				"powerup": 1500.0,  # Much higher
				"aggression": 300.0,  # Increased
				"exploration": 500.0,  # Much higher
				"escape_route": 80.0,
				"proximity_penalty": -100.0,
				"idle_penalty": -80.0,
				"trap_bonus": 350.0,  # Increased
				"bomb_frequency": 0.45,  # Increased
				"reaction_delay": 0.03,  # Much faster
				"pathfinding_frequency": 0.25  # Faster
			}
		
		Type.CHAOS:
			return {
				"safety": 600.0,  # Increased
				"danger_penalty": -7000.0,  # Less crazy
				"powerup": 600.0,
				"aggression": 900.0,  # Higher
				"exploration": 350.0,  # Increased
				"escape_route": 25.0,  # Increased
				"proximity_penalty": 0.0,
				"idle_penalty": -250.0,
				"trap_bonus": 700.0,  # Higher
				"bomb_frequency": 0.8,  # Even more bombs
				"reaction_delay": 0.01,  # 10ms - instant
				"pathfinding_frequency": 0.15  # Very fast
			}
		
		Type.DEFENSIVE:
			return {
				"safety": 2500.0,  # Extreme safety priority
				"danger_penalty": -20000.0,  # Massive danger avoidance
				"powerup": 400.0,
				"aggression": 50.0,  # Minimal aggression
				"exploration": 150.0,  # Low exploration
				"escape_route": 300.0,  # Requires multiple escapes
				"proximity_penalty": -800.0,  # Avoids opponents heavily
				"idle_penalty": -20.0,  # Comfortable waiting
				"trap_bonus": 100.0,  # Only traps if cornered
				"bomb_frequency": 0.15,  # Rarely bombs
				"reaction_delay": 0.09,  # 90ms - cautious
				"pathfinding_frequency": 0.5  # Slow, deliberate
			}
		
		Type.KAMIKAZE:
			return {
				"safety": 200.0,  # Minimal safety concern
				"danger_penalty": -3000.0,  # Willing to die
				"powerup": 150.0,  # Doesn't care about power-ups
				"aggression": 1500.0,  # Maximum aggression
				"exploration": 100.0,
				"escape_route": 0.0,  # No escape needed
				"proximity_penalty": 500.0,  # WANTS to be close (positive!)
				"idle_penalty": -400.0,  # Hates waiting
				"trap_bonus": 2000.0,  # Massive trap value, even if suicidal
				"bomb_frequency": 0.95,  # Almost always bombing
				"reaction_delay": 0.005,  # 5ms - nearly instant
				"pathfinding_frequency": 0.1  # Very aggressive pathing
			}
		
		Type.STRATEGIC:
			return {
				"safety": 1200.0,  # Good safety awareness
				"danger_penalty": -12000.0,
				"powerup": 800.0,  # Values power-ups strategically
				"aggression": 600.0,  # Measured aggression
				"exploration": 400.0,  # Systematic exploration
				"escape_route": 150.0,  # Always has exit plan
				"proximity_penalty": -200.0,
				"idle_penalty": -40.0,  # Patient
				"trap_bonus": 900.0,  # High trap value, calculated
				"bomb_frequency": 0.5,  # Balanced bombing
				"reaction_delay": 0.04,  # 40ms - thinking time
				"pathfinding_frequency": 0.8  # Plans further ahead
			}
		
		Type.TRAPPER:
			return {
				"safety": 900.0,  # Moderate safety
				"danger_penalty": -10000.0,
				"powerup": 500.0,
				"aggression": 500.0,  # Patient hunter
				"exploration": 250.0,
				"escape_route": 100.0,
				"proximity_penalty": -300.0,  # Keeps distance for ambush
				"idle_penalty": 0.0,  # COMFORTABLE waiting (no penalty)
				"trap_bonus": 1800.0,  # Extreme trap focus
				"bomb_frequency": 0.3,  # Selective bombing
				"reaction_delay": 0.06,  # 60ms - observant
				"pathfinding_frequency": 0.4  # Methodical
			}
		
		Type.LEARNED:
			return {
				"safety": 1000.0,
				"danger_penalty": -10000.0,
				"powerup": 700.0,
				"aggression": 700.0,  # Learns optimal aggression
				"exploration": 400.0,
				"escape_route": 100.0,
				"proximity_penalty": -100.0,
				"idle_penalty": -30.0,
				"trap_bonus": 800.0,  # Learns trap values
				"bomb_frequency": 0.5,  # Learned frequency
				"reaction_delay": 0.03,  # 30ms - Fast learning
				"pathfinding_frequency": 0.3,  # Adaptive
				"use_q_learning": true  # Special flag
			}
		
		Type.PERFECT:
			return {
				"safety": 1500.0,
				"danger_penalty": -12000.0,
				"powerup": 900.0,
				"aggression": 800.0,  # Calculates optimal aggression
				"exploration": 500.0,
				"escape_route": 120.0,
				"proximity_penalty": -150.0,
				"idle_penalty": -40.0,
				"trap_bonus": 1000.0,  # Perfect trap calculation
				"bomb_frequency": 0.6,  # Optimal frequency
				"reaction_delay": 0.05,  # 50ms - Simulation time
				"pathfinding_frequency": 0.2,  # Plans ahead
				"use_mcts": true  # Special flag
			}
		
		_:
			push_error("Unknown personality type: " + str(personality_type))
			return get_weights(Type.BALANCED)

static func get_personality_name(personality_type: Type) -> String:
	match personality_type:
		Type.BALANCED: return "Balanced"
		Type.AGGRESSIVE: return "Aggressive"
		Type.TIMID: return "Timid"
		Type.GREEDY: return "Greedy"
		Type.CHAOS: return "Chaos"
		Type.DEFENSIVE: return "Defensive"
		Type.KAMIKAZE: return "Kamikaze"
		Type.STRATEGIC: return "Strategic"
		Type.TRAPPER: return "Trapper"
		Type.LEARNED: return "Learned"
		Type.PERFECT: return "Perfect"
		_: return "Unknown"

static func get_random_personality() -> Type:
	return Type.values()[randi() % Type.size()]

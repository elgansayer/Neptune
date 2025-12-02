extends Resource
class_name ItemData

## Data-driven item resource for Saturn Bomberman pickup mechanics
## Based on Engineering Deconstruction Specification section 5.1
##
## This resource defines the schema for an item, allowing designers
## to create new items via the Inspector without touching code.

enum ItemType {
	FIRE,       # Fire Up: Increments ExplosionRadius by 1 (Max: 16)
	BOMB,       # Bomb Up: Increments MaxSimultaneousBombs by 1 (Max: 10)
	SPEED,      # Speed Up: Increments SpeedIndex through lookup table (Max: 8)
	KICK,       # Bomb Kick: Boolean flag - enables bomb displacement
	GLOVE,      # Power Glove: Boolean flag - enables bomb lifting/throwing
	FULL_FIRE,  # Full Fire: Sets ExplosionRadius to Max immediately
	EGG,        # Tirra Egg: Mode change - spawns dinosaur mount
	CURSE       # Geta (Clogs): Punishment - sets SpeedIndex to 0
}

@export_group("Visuals")
@export var display_name: String = ""
@export var texture: Texture2D
@export var idle_frame_coords: Vector2i = Vector2i.ZERO
@export var is_animated: bool = true

@export_group("Mechanics")
@export var type: ItemType = ItemType.FIRE
@export var stat_modifier: int = 1
@export var duration: float = 0.0  # 0 = permanent

@export_group("Audio")
@export var sfx_pickup: AudioStream
@export var voice_line: AudioStream  # For special items like "Full Fire!"

## Maps ItemType to ServerPowerUp.PowerUpType enum value
func get_server_type() -> int:
	match type:
		ItemType.BOMB:
			return 0  # BOMB_INCREASE
		ItemType.FIRE:
			return 1  # RANGE_INCREASE
		ItemType.SPEED:
			return 2  # SPEED_INCREASE
		ItemType.KICK:
			return 3  # BOMB_KICKER
		ItemType.GLOVE:
			return 4  # POWER_GLOVE
		ItemType.CURSE:
			return 5  # VIRUS
		_:
			return 0

## Get the animation name for this item type
func get_animation_name() -> String:
	match type:
		ItemType.BOMB:
			return "bomb"
		ItemType.FIRE:
			return "fire"
		ItemType.SPEED:
			return "skate"
		ItemType.KICK:
			return "kickbomb"
		ItemType.GLOVE:
			return "pglove"
		ItemType.CURSE:
			return "skull"
		ItemType.FULL_FIRE:
			return "fire"  # Uses fire sprite with different modulate
		ItemType.EGG:
			return "egg"
		_:
			return "bomb"

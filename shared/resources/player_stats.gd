class_name PlayerStats
extends RefCounted

## Saturn Bomberman Player Stats
##
## This class encapsulates all player stats with proper limits per the
## Saturn Bomberman competitive specification. Stats are modified by
## powerup collection and track current values vs limits.
##
## === Saturn Bomberman Stat Limits ===
## Bomb Count:  1 to 10 (default 1)
## Fire Range:  1 to 8 (16 with Full Fire)
## Speed Level: 1 to 8 (default 1)
## 
## === Special Items (Boolean) ===
## - Bomb Kick: Can kick bombs
## - Power Glove: Can pick up and throw bombs
## - Line Bomb: Places all bombs in a row
## - Power Bomb: Bombs pierce soft blocks
## - Heart: Extra life (competitive mode only)
## - Geta (Slow Shoes): Speed reduced (negative item)
##
## === Bomb Types ===
## NORMAL:  Standard bomb
## REMOTE:  Detonated manually with action button
## RUBBER:  Bounces off walls
## PIERCE:  Explosion passes through soft blocks

const Constants = preload("res://shared/constants.gd")

# Bomb type enum
enum BombType {
    NORMAL,
    REMOTE,
    RUBBER,
    PIERCE
}

# Virus type enum for skull effects (Saturn Bomberman)
enum VirusType {
    NONE,
    SPEEDSTER,        # Move at maximum speed (hard to control)
    SLOWPOKE,         # Move at minimum speed
    DIARRHOEA,        # Constantly drop bombs
    CONSTIPATION,     # Cannot place bombs
    SMALL_FLAME,      # Fire range reduced to 1
    UNSTOPPABLE,      # Player can't stop moving
    REVERSE,          # Controls are reversed
    HASTY_FUSE,       # Bombs explode very quickly (~1s)
    LEISURELY_FUSE,   # Bombs have long fuse (5-6s)
    RANDOM            # Random effect each time infected
}

# === Core Stats ===
var bomb_count: int = 1:
    set(value):
        bomb_count = clampi(value, Constants.BOMB_MIN, Constants.BOMB_MAX)
        
var fire_range: int = 2:
    set(value):
        # Full fire allows up to 16, otherwise cap at 8
        var max_range = Constants.FIRE_MAX_FULL if _has_full_fire else Constants.FIRE_MAX
        fire_range = clampi(value, Constants.FIRE_MIN, max_range)
        
var speed_level: int = 1:
    set(value):
        speed_level = clampi(value, Constants.SPEED_MIN, Constants.SPEED_MAX)

# === Ability Flags ===
var has_kick: bool = false
var has_glove: bool = false
var has_line_bomb: bool = false
var has_power_bomb: bool = false
var has_heart: bool = false  # Extra life in competitive mode

# === Internal Flags ===
var _has_full_fire: bool = false  # Unlocks fire_range cap to 16

# === Bomb Type ===
var bomb_type: BombType = BombType.NORMAL

# === Virus State (Saturn Bomberman) ===
var is_infected: bool = false
var virus_type: VirusType = VirusType.NONE
var virus_duration: float = 0.0
const VIRUS_DURATION_DEFAULT: float = 12.0  # 12 seconds per virus (Saturn spec)

# === Speed Calculation (Saturn Bomberman Sub-Pixel System) ===
# Saturn uses a sub-pixel accumulator for smooth speed transitions
var _speed_accumulator: int = 0

func get_speed_multiplier() -> float:
    """Get the effective speed multiplier based on speed_level and virus state"""
    if is_infected:
        match virus_type:
            VirusType.SLOWPOKE:
                return GameConfig.get_skate_speed_multiplier(0)  # Minimum speed
            VirusType.SPEEDSTER:
                return GameConfig.get_skate_speed_multiplier(Constants.SPEED_MAX)  # Max speed
    
    # Convert speed_level (1-8) to skate_count (0-7) for Saturn system
    var skate_count = speed_level - 1
    return GameConfig.get_skate_speed_multiplier(skate_count)

# === Stat Modification Methods ===

func add_bomb() -> bool:
    """Add +1 bomb capacity. Returns true if stat changed."""
    var old_value = bomb_count
    bomb_count += 1
    return bomb_count != old_value

func add_fire() -> bool:
    """Add +1 fire range. Returns true if stat changed."""
    var old_value = fire_range
    fire_range += 1
    return fire_range != old_value

func add_speed() -> bool:
    """Add +1 speed level. Returns true if stat changed."""
    var old_value = speed_level
    speed_level += 1
    return speed_level != old_value

func set_full_fire() -> bool:
    """Enable full fire (max range 16). Returns true if newly enabled."""
    if _has_full_fire:
        return false
    _has_full_fire = true
    fire_range = Constants.FIRE_MAX_FULL  # Immediately set to max
    return true

func enable_kick() -> bool:
    """Enable bomb kicking. Returns true if newly enabled."""
    if has_kick:
        return false
    has_kick = true
    return true

func enable_glove() -> bool:
    """Enable power glove. Returns true if newly enabled."""
    if has_glove:
        return false
    has_glove = true
    return true

func enable_line_bomb() -> bool:
    """Enable line bomb ability. Returns true if newly enabled."""
    if has_line_bomb:
        return false
    has_line_bomb = true
    return true

func enable_power_bomb() -> bool:
    """Enable power bomb (piercing). Returns true if newly enabled."""
    if has_power_bomb:
        return false
    has_power_bomb = true
    return true

func add_heart() -> bool:
    """Add heart (extra life). Returns true if newly added."""
    if has_heart:
        return false
    has_heart = true
    return true

func set_bomb_type(type: BombType) -> bool:
    """Set bomb type. Returns true if type changed."""
    if bomb_type == type:
        return false
    bomb_type = type
    return true

# === Negative Items ===

func apply_geta() -> void:
    """Apply Geta (slow shoes) - reduces speed level by 1"""
    speed_level = max(1, speed_level - 1)

func apply_virus(type: VirusType = VirusType.RANDOM) -> void:
    """Apply virus effect from skull pickup"""
    is_infected = true
    virus_duration = VIRUS_DURATION_DEFAULT
    
    if type == VirusType.RANDOM:
        # Random virus (excluding NONE and RANDOM itself)
        var virus_options = [
            VirusType.SPEEDSTER,
            VirusType.SLOWPOKE,
            VirusType.DIARRHOEA,
            VirusType.CONSTIPATION,
            VirusType.SMALL_FLAME,
            VirusType.UNSTOPPABLE,
            VirusType.REVERSE,
            VirusType.HASTY_FUSE,
            VirusType.LEISURELY_FUSE
        ]
        virus_type = virus_options[randi() % virus_options.size()]
    else:
        virus_type = type

func update_virus(delta: float) -> void:
    """Update virus timer. Call every frame."""
    if is_infected:
        virus_duration -= delta
        if virus_duration <= 0.0:
            clear_virus()

func clear_virus() -> void:
    """Clear virus effect"""
    is_infected = false
    virus_type = VirusType.NONE
    virus_duration = 0.0

func transfer_virus_to(other: PlayerStats) -> void:
    """Transfer virus to another player (touching while infected)"""
    if not is_infected:
        return
    
    other.is_infected = true
    other.virus_type = virus_type
    other.virus_duration = virus_duration
    
    clear_virus()

# === Serialization (for network sync) ===

func to_dict() -> Dictionary:
    """Serialize stats to dictionary for network transmission"""
    return {
        "bomb_count": bomb_count,
        "fire_range": fire_range,
        "speed_level": speed_level,
        "has_kick": has_kick,
        "has_glove": has_glove,
        "has_line_bomb": has_line_bomb,
        "has_power_bomb": has_power_bomb,
        "has_heart": has_heart,
        "has_full_fire": _has_full_fire,
        "bomb_type": bomb_type,
        "is_infected": is_infected,
        "virus_type": virus_type,
        "virus_duration": virus_duration
    }

func from_dict(data: Dictionary) -> void:
    """Deserialize stats from dictionary"""
    bomb_count = data.get("bomb_count", 1)
    fire_range = data.get("fire_range", 2)
    speed_level = data.get("speed_level", 1)
    has_kick = data.get("has_kick", false)
    has_glove = data.get("has_glove", false)
    has_line_bomb = data.get("has_line_bomb", false)
    has_power_bomb = data.get("has_power_bomb", false)
    has_heart = data.get("has_heart", false)
    _has_full_fire = data.get("has_full_fire", false)
    bomb_type = data.get("bomb_type", BombType.NORMAL)
    is_infected = data.get("is_infected", false)
    virus_type = data.get("virus_type", VirusType.NONE)
    virus_duration = data.get("virus_duration", 0.0)

# === Debugging ===

func _to_string() -> String:
    var bomb_type_names = ["NORMAL", "REMOTE", "RUBBER", "PIERCE"]
    return "PlayerStats(bombs=%d fire=%d speed=%d kick=%s glove=%s bomb_type=%s)" % [
        bomb_count, fire_range, speed_level, has_kick, has_glove,
        bomb_type_names[bomb_type]
    ]

# === Reset to Defaults ===

func reset_to_default() -> void:
    """Reset all stats to default values"""
    bomb_count = 1
    fire_range = 2
    speed_level = 1
    has_kick = false
    has_glove = false
    has_line_bomb = false
    has_power_bomb = false
    has_heart = false
    _has_full_fire = false
    bomb_type = BombType.NORMAL
    clear_virus()

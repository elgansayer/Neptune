extends CanvasLayer
class_name GameHUD

# In-Game HUD displaying match timer, player stats, and game status
# Shows critical information: time remaining, bombs available, power-up effects

@onready var match_timer: Label = $TopBar/MatchTimer
@onready var players_alive: Label = $TopBar/PlayersAlive
@onready var player_name: Label = $BottomLeft/PlayerName
@onready var bomb_label: Label = $BottomLeft/BombCount/BombLabel
@onready var range_label: Label = $BottomLeft/RangeIndicator/RangeLabel
@onready var speed_label: Label = $BottomLeft/SpeedIndicator/SpeedLabel

func _ready():
	# Ensure HUD is always on top
	layer = 100

func update_timer(time_remaining: float):
	"""Update match timer display with minutes:seconds format"""
	if time_remaining < 0:
		time_remaining = 0
	
	var minutes = int(time_remaining / 60)
	var seconds = int(time_remaining) % 60
	match_timer.text = "%d:%02d" % [minutes, seconds]
	
	# Warning color when time is running out
	if time_remaining <= 30:
		match_timer.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))  # Red
	elif time_remaining <= 60:
		match_timer.add_theme_color_override("font_color", Color(1.0, 0.8, 0.0))  # Yellow
	else:
		match_timer.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0))  # White

func update_players_alive(alive: int, total: int):
	"""Update alive player count"""
	players_alive.text = "%d / %d Players" % [alive, total]

func update_player_stats(bombs_current: int, bombs_max: int, range: int, speed_mult: float):
	"""Update local player's stats display"""
	var bombs_available = bombs_max - bombs_current
	bomb_label.text = "%d / %d" % [bombs_available, bombs_max]
	range_label.text = "Range: %d" % range
	speed_label.text = "Speed: %d%%" % int(speed_mult * 100)

func set_player_name(name: String):
	"""Set the local player's name display"""
	player_name.text = name

func show_game_over(winner_name: String):
	"""Display game over screen with winner"""
	# TODO: Create proper game over overlay
	match_timer.text = "GAME OVER"
	if winner_name:
		players_alive.text = "Winner: %s" % winner_name
	else:
		players_alive.text = "Draw!"

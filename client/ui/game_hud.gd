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

var countdown_label: Label = null
var countdown_bg: ColorRect = null
var last_countdown_value := -1

func _ready():
	# Ensure HUD is always on top
	layer = 100
	
	# Create semi-transparent background for countdown
	countdown_bg = ColorRect.new()
	countdown_bg.name = "CountdownBackground"
	countdown_bg.color = Color(0.0, 0.0, 0.0, 0.0)  # Start transparent
	countdown_bg.anchor_left = 0.0
	countdown_bg.anchor_top = 0.0
	countdown_bg.anchor_right = 1.0
	countdown_bg.anchor_bottom = 1.0
	countdown_bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	countdown_bg.visible = false
	add_child(countdown_bg)
	
	# Create countdown label (centered, large text)
	countdown_label = Label.new()
	countdown_label.name = "CountdownLabel"
	countdown_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	countdown_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	countdown_label.anchor_left = 0.5
	countdown_label.anchor_top = 0.5
	countdown_label.anchor_right = 0.5
	countdown_label.anchor_bottom = 0.5
	countdown_label.offset_left = -300
	countdown_label.offset_top = -150
	countdown_label.offset_right = 300
	countdown_label.offset_bottom = 150
	countdown_label.add_theme_font_size_override("font_size", 120)
	countdown_label.pivot_offset = Vector2(300, 150)
	countdown_label.visible = false
	add_child(countdown_label)

func show_countdown(time_remaining: float):
	"""Display animated countdown before match starts"""
	if not countdown_label:
		return
	
	var seconds = ceil(time_remaining)
	
	# Trigger "GO!" when countdown is nearly done (below 0.3s) but hasn't shown GO yet
	if time_remaining <= 0.3 and last_countdown_value != -999:
		last_countdown_value = -999  # Special value to mark "GO!" as shown
		
		# Show "GO!" with green color and bigger animation
		countdown_label.visible = true
		countdown_label.text = "GO!"
		countdown_label.scale = Vector2(0.3, 0.3)
		countdown_label.modulate = Color(0.2, 1.0, 0.2, 0.0)  # Start transparent green
		
		# Explosive animation
		var tween = create_tween()
		tween.set_parallel(true)
		tween.tween_property(countdown_label, "scale", Vector2(1.5, 1.5), 0.3).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_ELASTIC)
		tween.tween_property(countdown_label, "modulate", Color(0.0, 1.0, 0.0, 1.0), 0.2)
		tween.chain()
		# Fade out background and label
		tween.set_parallel(true)
		tween.tween_property(countdown_label, "modulate", Color(0.0, 1.0, 0.0, 0.0), 0.5).set_delay(0.3)
		tween.tween_property(countdown_bg, "color", Color(0.0, 0.0, 0.0, 0.0), 0.5).set_delay(0.3)
		tween.chain()
		tween.tween_callback(func():
			countdown_label.visible = false
			countdown_bg.visible = false
			last_countdown_value = -1
		)
		return
	
	# Only animate on value change for numbers
	if int(seconds) != last_countdown_value and seconds > 0:
		last_countdown_value = int(seconds)
		
		# Show background
		countdown_bg.visible = true
		countdown_bg.color = Color(0.0, 0.0, 0.0, 0.5)
		
		# Show number countdown
		countdown_label.visible = true
		countdown_label.text = str(int(seconds))
		countdown_label.scale = Vector2(0.5, 0.5)
		countdown_label.modulate = Color(1.0, 1.0, 0.2, 0.0)  # Start transparent yellow
		
		# Animate: scale up and fade in
		var tween = create_tween()
		tween.set_parallel(true)
		tween.tween_property(countdown_label, "scale", Vector2(1.2, 1.2), 0.2).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_BACK)
		tween.tween_property(countdown_label, "modulate", Color(1.0, 0.8, 0.0, 1.0), 0.2)
		tween.chain()
		# Then slightly shrink
		tween.tween_property(countdown_label, "scale", Vector2(1.0, 1.0), 0.1)

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

func update_player_stats(bombs_current: int, bombs_max: int, bomb_range: int, speed_mult: float):
	"""Update local player's stats display"""
	var bombs_available = bombs_max - bombs_current
	bomb_label.text = "%d / %d" % [bombs_available, bombs_max]
	range_label.text = "Range: %d" % bomb_range
	speed_label.text = "Speed: %d%%" % int(speed_mult * 100)

func set_player_name(player_name_text: String):
	"""Set the local player's name display"""
	player_name.text = player_name_text

func show_game_over(winner_name: String):
	"""Display game over screen with winner"""
	# TODO: Create proper game over overlay
	match_timer.text = "GAME OVER"
	if winner_name:
		players_alive.text = "Winner: %s" % winner_name
	else:
		players_alive.text = "Draw!"

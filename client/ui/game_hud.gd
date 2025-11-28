extends CanvasLayer
class_name GameHUD

# In-Game HUD displaying match timer, player stats, and game status
# Shows critical information: time remaining, bombs available, power-up effects
# Also handles spectator mode when local player is eliminated

@onready var match_timer: Label = $TopBar/MatchTimer
@onready var players_alive: Label = $TopBar/PlayersAlive
@onready var player_name: Label = $BottomLeft/PlayerName
@onready var bomb_label: Label = $BottomLeft/BombCount/BombLabel
@onready var range_label: Label = $BottomLeft/RangeIndicator/RangeLabel
@onready var speed_label: Label = $BottomLeft/SpeedIndicator/SpeedLabel

var countdown_label: Label = null
var countdown_bg: ColorRect = null
var last_countdown_value := -1

# Spectator mode UI elements
var spectator_overlay: ColorRect = null
var spectator_label: Label = null
var is_spectating := false

# Hurry mode UI elements
var hurry_overlay: ColorRect = null
var hurry_label: Label = null
var hurry_mode_shown := false

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
	
	# Create spectator mode overlay (semi-transparent top bar)
	spectator_overlay = ColorRect.new()
	spectator_overlay.name = "SpectatorOverlay"
	spectator_overlay.color = Color(0.0, 0.0, 0.0, 0.7)
	spectator_overlay.anchor_left = 0.0
	spectator_overlay.anchor_top = 0.0
	spectator_overlay.anchor_right = 1.0
	spectator_overlay.anchor_bottom = 0.0
	spectator_overlay.offset_top = 60  # Below TopBar
	spectator_overlay.offset_bottom = 120
	spectator_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	spectator_overlay.visible = false
	add_child(spectator_overlay)
	
	# Create spectator label
	spectator_label = Label.new()
	spectator_label.name = "SpectatorLabel"
	spectator_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	spectator_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	spectator_label.anchor_left = 0.0
	spectator_label.anchor_top = 0.0
	spectator_label.anchor_right = 1.0
	spectator_label.anchor_bottom = 1.0
	spectator_label.add_theme_font_size_override("font_size", 28)
	spectator_label.add_theme_color_override("font_color", Color(1.0, 0.8, 0.2))  # Gold color
	spectator_label.text = "💀 YOU HAVE BEEN ELIMINATED - SPECTATING 💀"
	spectator_overlay.add_child(spectator_label)
	
	# Create hurry mode overlay (flashing warning at top)
	hurry_overlay = ColorRect.new()
	hurry_overlay.name = "HurryOverlay"
	hurry_overlay.color = Color(1.0, 0.0, 0.0, 0.8)
	hurry_overlay.anchor_left = 0.0
	hurry_overlay.anchor_top = 0.0
	hurry_overlay.anchor_right = 1.0
	hurry_overlay.anchor_bottom = 0.0
	hurry_overlay.offset_bottom = 80
	hurry_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hurry_overlay.visible = false
	add_child(hurry_overlay)
	
	# Create hurry label
	hurry_label = Label.new()
	hurry_label.name = "HurryLabel"
	hurry_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hurry_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	hurry_label.anchor_left = 0.0
	hurry_label.anchor_top = 0.0
	hurry_label.anchor_right = 1.0
	hurry_label.anchor_bottom = 1.0
	hurry_label.add_theme_font_size_override("font_size", 48)
	hurry_label.add_theme_color_override("font_color", Color(1.0, 1.0, 0.0))  # Yellow
	hurry_label.text = "⚠️ HURRY UP! ⚠️"
	hurry_overlay.add_child(hurry_label)

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

func show_hurry_mode():
	"""Display HURRY UP warning when hurry mode is triggered"""
	if hurry_mode_shown:
		return  # Already shown
	hurry_mode_shown = true
	
	if not hurry_overlay:
		return
	
	# Show with dramatic animation
	hurry_overlay.visible = true
	hurry_overlay.modulate = Color(1, 1, 1, 0)
	hurry_label.scale = Vector2(0.5, 0.5)
	hurry_label.pivot_offset = hurry_label.size / 2
	
	# Flash animation
	var tween = create_tween()
	tween.set_parallel(true)
	tween.tween_property(hurry_overlay, "modulate", Color(1, 1, 1, 1), 0.2)
	tween.tween_property(hurry_label, "scale", Vector2(1.2, 1.2), 0.3).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_ELASTIC)
	tween.chain()
	tween.tween_property(hurry_label, "scale", Vector2(1.0, 1.0), 0.1)
	
	# Start flashing loop
	_start_hurry_flash()
	
	# Update timer display text
	match_timer.text = "HURRY!"
	match_timer.add_theme_color_override("font_color", Color(1.0, 0.0, 0.0))  # Red
	
	print("[HUD] HURRY UP mode activated!")

var hurry_flash_tween: Tween = null

func _start_hurry_flash():
	"""Create looping flash animation for hurry mode"""
	if hurry_flash_tween and hurry_flash_tween.is_valid():
		hurry_flash_tween.kill()
	
	hurry_flash_tween = create_tween()
	hurry_flash_tween.set_loops()  # Loop forever
	hurry_flash_tween.tween_property(hurry_overlay, "color", Color(1.0, 0.0, 0.0, 0.9), 0.3)
	hurry_flash_tween.tween_property(hurry_overlay, "color", Color(0.8, 0.0, 0.0, 0.6), 0.3)

func hide_hurry_mode():
	"""Hide hurry mode warning"""
	hurry_mode_shown = false
	if hurry_flash_tween and hurry_flash_tween.is_valid():
		hurry_flash_tween.kill()
	if hurry_overlay:
		hurry_overlay.visible = false

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

func show_spectator_mode():
	"""Show spectator mode overlay when local player is eliminated"""
	if is_spectating:
		return  # Already spectating
	
	is_spectating = true
	
	# Hide player stats (they're dead)
	$BottomLeft.visible = false
	
	# Show spectator overlay with animation
	if spectator_overlay:
		spectator_overlay.visible = true
		spectator_overlay.modulate = Color(1, 1, 1, 0)
		# Tween is automatically cleaned up when complete or when node is freed
		create_tween().tween_property(spectator_overlay, "modulate", Color(1, 1, 1, 1), 0.5)
	
	print("[HUD] Entered spectator mode")

func hide_spectator_mode():
	"""Hide spectator mode overlay (for next round or restart)"""
	is_spectating = false
	$BottomLeft.visible = true
	if spectator_overlay:
		spectator_overlay.visible = false

# Game over state tracking
var game_over_shown := false

func show_game_over(winner_name: String):
	"""Display game over screen with winner"""
	# Prevent duplicate game over screens
	if game_over_shown:
		return
	game_over_shown = true
	
	# Hide spectator overlay if showing
	if spectator_overlay:
		spectator_overlay.visible = false
	
	# Remove any existing game over elements
	var existing_bg = get_node_or_null("GameOverBackground")
	if existing_bg:
		existing_bg.queue_free()
	var existing_label = get_node_or_null("GameOverLabel")
	if existing_label:
		existing_label.queue_free()
	var existing_winner = get_node_or_null("WinnerLabel")
	if existing_winner:
		existing_winner.queue_free()
	
	# Create game over overlay
	var game_over_bg = ColorRect.new()
	game_over_bg.name = "GameOverBackground"
	game_over_bg.color = Color(0.0, 0.0, 0.0, 0.8)
	game_over_bg.anchor_left = 0.0
	game_over_bg.anchor_top = 0.0
	game_over_bg.anchor_right = 1.0
	game_over_bg.anchor_bottom = 1.0
	game_over_bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(game_over_bg)
	
	# Create game over label
	var game_over_label = Label.new()
	game_over_label.name = "GameOverLabel"
	game_over_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	game_over_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	game_over_label.anchor_left = 0.5
	game_over_label.anchor_top = 0.3
	game_over_label.anchor_right = 0.5
	game_over_label.anchor_bottom = 0.3
	game_over_label.offset_left = -300
	game_over_label.offset_top = -50
	game_over_label.offset_right = 300
	game_over_label.offset_bottom = 50
	game_over_label.add_theme_font_size_override("font_size", 72)
	game_over_label.add_theme_color_override("font_color", Color(1.0, 0.8, 0.0))  # Gold
	game_over_label.text = "GAME OVER"
	add_child(game_over_label)
	
	# Create winner label
	var winner_label = Label.new()
	winner_label.name = "WinnerLabel"
	winner_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	winner_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	winner_label.anchor_left = 0.5
	winner_label.anchor_top = 0.5
	winner_label.anchor_right = 0.5
	winner_label.anchor_bottom = 0.5
	winner_label.offset_left = -400
	winner_label.offset_top = -30
	winner_label.offset_right = 400
	winner_label.offset_bottom = 30
	winner_label.add_theme_font_size_override("font_size", 48)
	
	if winner_name:
		winner_label.text = "🏆 Winner: %s 🏆" % winner_name
		winner_label.add_theme_color_override("font_color", Color(0.2, 1.0, 0.2))  # Green
	else:
		winner_label.text = "💀 DRAW - No Survivors! 💀"
		winner_label.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))  # Red
	
	add_child(winner_label)
	
	# Animate the game over screen
	# Tweens are automatically cleaned up when complete or when node is freed
	game_over_bg.modulate = Color(1, 1, 1, 0)
	game_over_label.modulate = Color(1, 1, 1, 0)
	winner_label.modulate = Color(1, 1, 1, 0)
	
	var tween = create_tween()
	tween.set_parallel(true)
	tween.tween_property(game_over_bg, "modulate", Color(1, 1, 1, 1), 0.5)
	tween.tween_property(game_over_label, "modulate", Color(1, 1, 1, 1), 0.5).set_delay(0.2)
	tween.tween_property(winner_label, "modulate", Color(1, 1, 1, 1), 0.5).set_delay(0.5)
	
	# Also update the top bar
	match_timer.text = "GAME OVER"
	if winner_name:
		players_alive.text = "Winner: %s" % winner_name
	else:
		players_alive.text = "Draw!"

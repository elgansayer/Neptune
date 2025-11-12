extends CanvasLayer
class_name GameHUD

# Simplified HUD for 9/10-Player Widescreen Battle Mode
# =======================================================
# Designed to be minimal and non-obstructive for large multiplayer battles.
#
# Visual Specification (based on classic Bomberman Saturn aesthetic):
# - TIME LIMIT: Top center, bright white/yellow digital numbers (3:00 format)
# - ROUND SCORE TALLY: Diamond icons flanking timer, player-colored
# - PLAYER IDENTIFIERS: Small portraits on left/right edges with player colors
# - NO item counters (bomb/range/speed) to minimize HUD clutter
#
# Color Palette:
# - Timer: Bright white (>60s), yellow (60-30s), red (<30s)
# - Background: Dark grey/black panels (0.1, 0.1, 0.15)
# - Borders: Teal/grey (0.3, 0.4, 0.5)
# - Text: High-contrast white with black shadow
#
# Font Style:
# - Clean, blocky digital font (36px for timer)
# - Centrally aligned for all numerical displays
# - No anti-aliasing for retro pixel aesthetic

@onready var match_timer: Label = $TopBar/TimerPanel/MatchTimer
@onready var left_score_tally: HBoxContainer = $TopBar/LeftScoreTally
@onready var right_score_tally: HBoxContainer = $TopBar/RightScoreTally
@onready var left_player_panel: VBoxContainer = $LeftPlayerPanel
@onready var right_player_panel: VBoxContainer = $RightPlayerPanel

# Player colors for round score indicators
const PLAYER_COLORS = [
	Color(1.0, 1.0, 1.0),  # White
	Color(0.2, 0.2, 0.2),  # Black
	Color(1.0, 0.2, 0.2),  # Red
	Color(0.2, 0.4, 1.0),  # Blue
	Color(1.0, 0.8, 0.2),  # Yellow
	Color(0.2, 1.0, 0.2),  # Green
	Color(1.0, 0.4, 0.8),  # Pink
	Color(0.6, 0.2, 1.0),  # Purple
	Color(1.0, 0.6, 0.2),  # Orange
	Color(0.2, 1.0, 1.0),  # Cyan
]

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
	
	# Warning color when time is running out (bright white/yellow/red)
	if time_remaining <= 30:
		match_timer.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))  # Red
	elif time_remaining <= 60:
		match_timer.add_theme_color_override("font_color", Color(1.0, 0.8, 0.0))  # Yellow
	else:
		match_timer.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0))  # White

func update_round_scores(player_scores: Dictionary):
	"""Update round score tally with player-colored icons
	player_scores: { player_id: rounds_won }
	"""
	# Clear existing icons
	for child in left_score_tally.get_children():
		child.queue_free()
	for child in right_score_tally.get_children():
		child.queue_free()
	
	# Sort players by ID for consistent ordering
	var player_ids = player_scores.keys()
	player_ids.sort()
	
	# Split players between left and right sides
	var mid = int(ceil(player_ids.size() / 2.0))
	var left_players = player_ids.slice(0, mid)
	var right_players = player_ids.slice(mid, player_ids.size())
	
	# Create icons for left side
	for player_id in left_players:
		var rounds_won = player_scores[player_id]
		for i in range(rounds_won):
			var icon = create_score_icon(get_player_color(player_id))
			left_score_tally.add_child(icon)
	
	# Create icons for right side
	for player_id in right_players:
		var rounds_won = player_scores[player_id]
		for i in range(rounds_won):
			var icon = create_score_icon(get_player_color(player_id))
			right_score_tally.add_child(icon)

func create_score_icon(color: Color) -> Control:
	"""Create a small colored trophy/diamond icon for round wins"""
	# Create a diamond shape using a Polygon2D
	var control = Control.new()
	control.custom_minimum_size = Vector2(16, 16)
	
	var polygon = Polygon2D.new()
	# Diamond/rhombus shape points
	var diamond_points = PackedVector2Array([
		Vector2(8, 2),   # Top
		Vector2(14, 8),  # Right
		Vector2(8, 14),  # Bottom
		Vector2(2, 8)    # Left
	])
	polygon.polygon = diamond_points
	polygon.color = color
	
	# Add a slight border for better visibility
	var outline = Line2D.new()
	outline.add_point(Vector2(8, 2))
	outline.add_point(Vector2(14, 8))
	outline.add_point(Vector2(8, 14))
	outline.add_point(Vector2(2, 8))
	outline.add_point(Vector2(8, 2))
	outline.width = 1.5
	outline.default_color = Color(0, 0, 0, 0.5)  # Dark outline
	
	control.add_child(outline)
	control.add_child(polygon)
	
	return control

func get_player_color(player_id: String) -> Color:
	"""Get color for a player based on their ID"""
	var hash_val = player_id.hash()
	var color_index = abs(hash_val) % PLAYER_COLORS.size()
	return PLAYER_COLORS[color_index]

func update_player_identifiers(players: Dictionary):
	"""Update player identifier portraits on edges
	players: { player_id: { username, color_index, ... } }
	"""
	# Clear existing identifiers
	for child in left_player_panel.get_children():
		child.queue_free()
	for child in right_player_panel.get_children():
		child.queue_free()
	
	# Sort players by ID for consistent ordering
	var player_ids = players.keys()
	player_ids.sort()
	
	# Split players between left and right sides
	var mid = int(ceil(player_ids.size() / 2.0))
	var left_players = player_ids.slice(0, mid)
	var right_players = player_ids.slice(mid, player_ids.size())
	
	# Create identifiers for left side
	for player_id in left_players:
		var player_data = players[player_id]
		var portrait = create_player_portrait(player_id, player_data)
		left_player_panel.add_child(portrait)
	
	# Create identifiers for right side
	for player_id in right_players:
		var player_data = players[player_id]
		var portrait = create_player_portrait(player_id, player_data)
		right_player_panel.add_child(portrait)

func create_player_portrait(player_id: String, player_data: Dictionary) -> PanelContainer:
	"""Create a small character portrait for player identification"""
	var container = PanelContainer.new()
	container.custom_minimum_size = Vector2(60, 70)
	
	# Create a dark panel style for player portraits
	var panel_style = StyleBoxFlat.new()
	panel_style.bg_color = Color(0.15, 0.15, 0.2, 0.9)  # Dark background
	panel_style.border_width_left = 2
	panel_style.border_width_top = 2
	panel_style.border_width_right = 2
	panel_style.border_width_bottom = 2
	panel_style.border_color = get_player_color(player_id)  # Player-colored border
	panel_style.corner_radius_top_left = 4
	panel_style.corner_radius_top_right = 4
	panel_style.corner_radius_bottom_right = 4
	panel_style.corner_radius_bottom_left = 4
	container.add_theme_stylebox_override("panel", panel_style)
	
	var vbox = VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 2)
	container.add_child(vbox)
	
	# Character portrait (colored square representing player)
	var portrait = ColorRect.new()
	portrait.custom_minimum_size = Vector2(40, 40)
	portrait.color = get_player_color(player_id)
	vbox.add_child(portrait)
	
	# Player name label with shadow for readability
	var label = Label.new()
	var username = player_data.get("username", "Player")
	label.text = username.substr(0, 8)  # Truncate long names
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 10)
	label.add_theme_color_override("font_color", Color(1, 1, 1, 1))
	label.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
	label.add_theme_constant_override("shadow_offset_x", 1)
	label.add_theme_constant_override("shadow_offset_y", 1)
	vbox.add_child(label)
	
	return container

func show_game_over(winner_name: String):
	"""Display game over screen with winner"""
	match_timer.text = "GAME OVER"
	if winner_name:
		# Could add a winner announcement overlay
		pass
	else:
		# Draw message
		pass

# Legacy methods for backwards compatibility (do nothing in simplified mode)
func update_players_alive(_alive: int, _total: int):
	pass

func update_player_stats(_bombs_current: int, _bombs_max: int, _range: int, _speed_mult: float):
	pass

func set_player_name(_name: String):
	pass

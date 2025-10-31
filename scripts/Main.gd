extends Node2D

@onready var connect_button = $ConnectButton
@onready var matchmake_button = $MatchmakeButton
@onready var status_label = $StatusLabel

var nakama_client = null

func _ready():
	print("Checking for NakamaService singleton...")
	
	# Access the autoload singleton directly by its name
	if NakamaService:
		print("NakamaService autoload found successfully.")
		nakama_client = NakamaService
		
		# Connect signals
		nakama_client.authenticated.connect(_on_nakama_authenticated)
		nakama_client.match_joined.connect(_on_nakama_match_joined)
		nakama_client.match_data_received.connect(_on_nakama_match_data_received)
		
		status_label.text = "Status: Ready to connect"
		print("NakamaService ready and signals connected.")
	else:
		status_label.text = "Error: NakamaService autoload not found."
		push_error("NakamaService autoload not accessible. Check Project Settings -> AutoLoad.")


func _on_ConnectButton_pressed():
	if nakama_client and nakama_client.init_client():
		status_label.text = "Status: Connecting..."
		# Use a dummy device ID for testing
		nakama_client.authenticate_device("test_device_id_123")

func _on_nakama_authenticated(session, is_new_user):
	status_label.text = "Status: Authenticated. User ID: " + session.user_id
	print("Authenticated: ", session.user_id, " New User: ", is_new_user)

func _on_MatchmakeButton_pressed():
	if nakama_client and nakama_client.session:
		status_label.text = "Status: Starting matchmaking..."
		# Query, min_users, max_users
		nakama_client.start_matchmaking("*", 2, 4) # Matchmake for 2-4 players
	else:
		status_label.text = "Status: Not authenticated. Connect first."

func _on_nakama_match_joined(match):
	status_label.text = "Status: Joined match: " + match.match_id
	print("Joined match: ", match.match_id)
	
	# Load the game scene after successfully joining match
	await get_tree().create_timer(0.5).timeout  # Small delay for connection to stabilize
	get_tree().change_scene_to_file("res://Game.tscn")

func _on_nakama_match_data_received(data):
	status_label.text = "Status: Match data received (OpCode: " + str(data.op_code) + ")"
	print("Match data received: ", data)

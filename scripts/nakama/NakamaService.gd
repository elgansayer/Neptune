# scripts/nakama/NakamaService.gd
extends Node

# Signal when authentication is successful
signal authenticated(session, is_new_user)
# Signal when the client successfully joins a real-time match
signal match_joined(match)
# Signal for real-time match data received
signal match_data_received(data)

const NAKAMA_IP = "127.0.0.1"
const NAKAMA_PORT = 7350
const NAKAMA_KEY = "defaultkey"

var client = null
var session = null
var socket = null
var match_id = ""

# --- Initialisation and Authentication ---

func init_client():
	# Check if Nakama autoload is available
	if not Nakama:
		push_error("Nakama Godot client library not loaded. Please ensure it is in the 'addons/' folder and configured in AutoLoad.")
		return false

	# Create client using the Nakama singleton's create_client method
	client = Nakama.create_client(NAKAMA_KEY, NAKAMA_IP, NAKAMA_PORT, "http")
	
	print("Nakama client initialised.")
	return true

func authenticate_device(device_id: String, create: bool = true):
	# Use device authentication for simplicity, but easily swapped for email/other.
	print("Attempting to authenticate...")
	# authenticate_device_async signature: (device_id: String, username: String = "", create: bool = true, vars: Dictionary = {})
	var attempts := 0
	var last_exception: Variant = null
	while attempts < 3:
		attempts += 1
		var auth_result = await client.authenticate_device_async(device_id, "", create)
		if not auth_result.is_exception():
			session = auth_result
			print("Authentication successful! User ID: " + session.user_id)
			authenticated.emit(session, session.created)
			await connect_socket()
			return
		else:
			last_exception = auth_result.exception
			push_warning("Authentication attempt %d failed: %s" % [attempts, str(last_exception)])
			# Small exponential backoff before retrying
			await get_tree().create_timer(0.5 * pow(2.0, attempts - 1)).timeout
	
	push_error("Authentication failed after retries: " + str(last_exception))
	return

# --- Real-Time Socket Connection ---

func connect_socket():
	if session == null:
		push_error("Cannot connect socket: Not authenticated.")
		return

	# Create socket using Nakama's create_socket_from (not create_socket_adapter)
	# This returns a NakamaSocket which has the high-level signals
	socket = Nakama.create_socket_from(client)
	
	# Connect signals first
	socket.received_match_state.connect(_on_match_data_received)
	socket.received_match_presence.connect(_on_match_presence)
	socket.connected.connect(_on_socket_connected)
	socket.closed.connect(_on_socket_closed)
	socket.received_error.connect(_on_socket_error)
	
	# Connect to Nakama server
	await socket.connect_async(session)
	print("Connecting socket...")

func _on_socket_connected():
	print("Socket connected successfully!")

func _on_socket_closed():
	print("Socket connection closed")

func _on_socket_error(err):
	push_error("Socket error: " + str(err))

# --- Matchmaking and Real-Time Match ---

func start_matchmaking(_query: String, _min_users: int, _max_users: int):
	print("Starting matchmaking...")
	
	# Call RPC to create authoritative match on server
	print("Calling RPC to create bomberman match...")
	var rpc_result = await client.rpc_async(session, "create_bomberman_match", "")
	
	if rpc_result.is_exception():
		push_error("Failed to create match via RPC: " + str(rpc_result.exception))
		return
	
	# Parse the match ID from RPC response
	var response = JSON.parse_string(rpc_result.payload)
	if not response or not response.has("matchId"):
		push_error("Invalid RPC response: " + str(rpc_result.payload))
		return
		
	var created_match_id = response["matchId"]
	print("RPC returned match ID: " + created_match_id)
	
	# Now join the match that was created
	print("Joining match...")
	var match_result = await socket.join_match_async(created_match_id)
	
	if match_result.is_exception():
		push_error("Failed to join match: " + str(match_result.exception))
		print("MATCH JOIN FAILED: ", match_result.exception)
		return
		
	match_id = match_result.match_id
	print("Joined match: " + match_id)
	print("Match label: '", match_result.label, "'")
	print("Match size: ", match_result.size)
	print("Match authoritative: ", match_result.authoritative)
	
	# This should now be authoritative!
	if not match_result.authoritative:
		push_error("ERROR: Got relayed match instead of authoritative!")
	else:
		print("SUCCESS: Match is authoritative!")
	
	match_joined.emit(match_result)

# --- Network Data Handling (Competitive Core) ---

# This function sends a minimal input packet
func send_player_input(input_data: Dictionary):
	if socket and match_id:
		# OpCode 1 is reserved for Client Input
		var payload = JSON.stringify(input_data)
		socket.send_match_state_async(match_id, 1, payload)

# This is where all network updates are received. OpCode 2 will be for State Sync.
func _on_match_data_received(match_state: NakamaRTAPI.MatchData):
	var data_string = match_state.data
	var parsed_data = JSON.parse_string(data_string)

	if match_state.op_code == 2: # State Sync OpCode
		# This will be processed by the GameManager to update ALL entities.
		match_data_received.emit({"op_code": match_state.op_code, "data": parsed_data})
	elif match_state.op_code == 1: # Input from other players
		# This will be handled by the GameManager for rollback/prediction
		pass # Not needed for initial setup, but noted for future development.
	else:
		push_warning("Received unknown OpCode: " + str(match_state.op_code))

# --- Presence Handling ---
func _on_match_presence(match_presence_event: NakamaRTAPI.MatchPresenceEvent):
	for user in match_presence_event.joins:
		print("Player joined: " + user.username)
	for user in match_presence_event.leaves:
		print("Player left: " + user.username)

# --- Global Access ---
func _ready():
	# Set this script as a globally available singleton (needs to be auto-loaded in Project Settings)
	set_process(true) # Ensure _process is called for async operations

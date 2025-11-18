extends Node

# Manages player lobbies and matchmaking
# Players can create/join rooms and ready up

signal lobby_updated(lobby_data: Dictionary)

class PlayerInfo:
	var peer_id: int
	var username: String
	var ready: bool = false
	var in_game: bool = false

var players = {}  # peer_id -> PlayerInfo
var lobbies = {}  # lobby_id -> Array[PlayerInfo]

func add_player(peer_id: int, username: String):
	var player = PlayerInfo.new()
	player.peer_id = peer_id
	player.username = username
	players[peer_id] = player
	print("[Lobby] Player added: ", username, " (", peer_id, ")")

func remove_player(peer_id: int):
	if players.has(peer_id):
		print("[Lobby] Player removed: ", players[peer_id].username)
		players.erase(peer_id)

func get_player(peer_id: int) -> PlayerInfo:
	return players.get(peer_id)

# TODO: Implement lobby creation, joining, ready system
# For now, just track connected players

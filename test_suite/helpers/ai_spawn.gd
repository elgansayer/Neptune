extends Node

const GameInstanceScript = preload("res://server/game_instance.gd")
const AIPlayerScript = preload("res://shared/entities/ai_player.gd")

func make_game(map_dict: Dictionary) -> Node2D:
	var game: Node2D = GameInstanceScript.new()
	game.test_mode = true  # Skip normal map loading
	add_child(game)  # Add to helper node instead of root
	await get_tree().process_frame  # allow _ready()
	# Override map deterministically after _ready
	game.load_custom_map(map_dict)
	return game

func spawn_ai(game: Node2D, personality: int, spawn_index:=0) -> Node2D:
	var bot_id = game.add_ai_bot(personality)
	var bot = game.players[bot_id]
	return bot

func spawn_dummy_player(game: Node2D, spawn_index:=1) -> Node2D:
	var pid = 500 + spawn_index
	game.add_player(pid, "Dummy"+str(pid))
	return game.players[pid]

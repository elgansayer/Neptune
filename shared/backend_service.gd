extends Node
class_name BackendService

# Abstract interface for backend services (local SQLite or PlayFab)
# This allows easy migration from local auth to PlayFab later

# Authentication
func authenticate(username: String, password: String) -> Dictionary:
	push_error("BackendService.authenticate() not implemented")
	return {"success": false, "error": "Not implemented"}

func register_user(username: String, password: String) -> Dictionary:
	push_error("BackendService.register_user() not implemented")
	return {"success": false, "error": "Not implemented"}

# Leaderboards
func get_leaderboard(leaderboard_name: String, max_results: int = 10) -> Array:
	push_error("BackendService.get_leaderboard() not implemented")
	return []

func submit_score(leaderboard_name: String, score: int) -> Dictionary:
	push_error("BackendService.submit_score() not implemented")
	return {"success": false}

# Player data
func save_player_data(user_id: String, data: Dictionary) -> Dictionary:
	push_error("BackendService.save_player_data() not implemented")
	return {"success": false}

func get_player_data(user_id: String) -> Dictionary:
	push_error("BackendService.get_player_data() not implemented")
	return {}

# Match results
func save_match_results(match_data: Dictionary) -> Dictionary:
	push_error("BackendService.save_match_results() not implemented")
	return {"success": false}

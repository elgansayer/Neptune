extends "res://tests/bot_test_suite.gd"

var hud: GameHUD

func setup_suite() -> void:
	pass

func teardown_suite() -> void:
	pass

func setup_test() -> void:
	hud = load("res://client/ui/game_hud.tscn").instantiate()
	add_child(hud)

func teardown_test() -> void:
	hud.queue_free()
	await get_tree().process_frame

func _slot(id: String) -> Control:
	return hud.player_face_slots[hud.player_face_mapping[id]]

func _badge(id: String) -> Label:
	return _slot(id).get_node("FaceViewport/BotBadge")

func test_authority_marks_bot_and_exposes_personality() -> Variant:
	hud.add_player_face("7", "Robin", 3, {"type": "bot", "personality": "DEFENSIVE"})
	return assert_true(_badge("7").visible and _badge("7").text == "BOT"
		and "Bot (Defensive)" in _slot("7").tooltip_text
		and _slot("7").get_node("Score").text == "3", "Bot badge must not replace score/personality information")

func test_names_and_negative_ids_do_not_identify_bots() -> Variant:
	hud.add_player_face("-5", "Bot_BALANCED", 0, {"type": "human"})
	hud.add_player_face("-6", "Bot_DEFENSIVE")
	return assert_true(not _badge("-5").visible and not _badge("-6").visible, "Only authority participant metadata identifies a bot")

func test_existing_slot_refreshes_identity_without_recreating_face() -> Variant:
	hud.add_player_face("1", "First", 0, {"type": "bot", "personality": "BALANCED"})
	var sprite = hud.player_face_sprites.get("1")
	hud.add_player_face("1", "Returning human", 0, {"type": "human"})
	return assert_true(not _badge("1").visible and _slot("1").tooltip_text == "Returning human"
		and hud.player_face_sprites.get("1") == sprite, "Roster updates must clear old identity without duplicating the face")

func test_twelve_participants_have_unique_faces_in_two_bounded_rows() -> Variant:
	for i in range(12):
		hud.add_player_face(str(i), "Player%d" % i, 0, {"type": "bot" if i % 2 else "human"})
	await get_tree().process_frame
	if hud.player_face_mapping.size() != 12 or hud.player_face_slots.size() != 12:
		return "Supported room participants were omitted"
	var slots := {}
	for i in range(12):
		var id := str(i)
		slots[hud.player_face_mapping[id]] = true
		if not _slot(id).visible or _badge(id).visible != bool(i % 2): return "Slot/badge identity leaked between participants"
		if _slot(id).position.x + _slot(id).size.x > hud.player_faces_container.size.x + 1:
			return "A participant face overflowed the roster width"
		if _slot(id).get_node("FaceViewport/SubViewport").get_child_count() != 1: return "Cloned slot copied another participant's sprite"
	return assert_true(slots.size() == 12 and hud.player_faces_container.columns == 6
		and hud.get_node("TopBar").offset_bottom == 44, "Twelve faces require two rows rather than overflowing a four-seat HUD")

func test_removed_and_reused_slots_clear_bot_metadata() -> Variant:
	hud.add_player_face("1", "Bot", 0, {"type": "bot", "personality": "AGGRESSIVE"})
	hud.remove_player_face("1")
	hud.add_player_face("2", "Human", 2, {"type": "human"})
	if _badge("2").visible or _slot("2").tooltip_text != "Human": return "Reused slot retained the removed bot identity"
	hud.clear_all_player_faces()
	return assert_true(hud.player_face_mapping.is_empty() and hud.player_face_sprites.is_empty()
		and hud.get_node("TopBar").offset_bottom == 24, "Clearing a roster must also reset layout")

func test_roster_snapshots_remove_absent_players_and_refresh_authority_labels() -> Variant:
	hud.update_player_roster({"1": {"username": "Human"}, "2": {}}, {"1": {"type": "human"}, "2": {"type": "bot", "personality": "DEFENSIVE"}})
	if hud.player_face_mapping.size() != 2 or not _badge("2").visible: return "Snapshot lost the authority bot identity"
	hud.update_player_roster({"2": {"username": "Replacement", "wins": 4}}, {"2": {"type": "human"}})
	return assert_true(not hud.player_face_mapping.has("1") and not _badge("2").visible
		and _slot("2").get_node("Score").text == "4" and _slot("2").tooltip_text == "Replacement", "Roster snapshots must remove stale faces and update identity/score")

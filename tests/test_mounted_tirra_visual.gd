extends "res://tests/bot_test_suite.gd"

var viewport: SubViewport
var view: Node2D

func setup_suite() -> void:
	pass

func teardown_suite() -> void:
	pass

func setup_test() -> void:
	viewport = SubViewport.new()
	viewport.size = Vector2i(320, 224)
	add_child(viewport)
	view = load("res://client/game_view.tscn").instantiate()
	view.set_script(load("res://tests/support/arena_view_fixture.gd"))
	viewport.add_child(view)

func teardown_test() -> void:
	viewport.queue_free()
	await get_tree().process_frame

func _player() -> Node2D:
	var player := Node2D.new()
	var sprite := AnimatedSprite2D.new()
	sprite.name = "AnimatedSprite2D"
	player.add_child(sprite)
	view.players_container.add_child(player)
	return player

func test_actual_pck_directional_mount_updates_preserve_frames_timing_and_phase() -> Variant:
	var player := _player()
	for level in range(3):
		var data := {"tirra_growth_level": level}
		view._manage_tirra_visual(player, true, data)
		var visual = player.get_node("TirraVisual")
		var sprite: AnimatedSprite2D = visual.get("_current_sprite")
		if sprite == null or sprite.sprite_frames == null: return "Actual PCK growth level lacks its active sprite"
		var frames := sprite.sprite_frames
		var inventory := {}
		for animation in frames.get_animation_names():
			inventory[animation] = {"frames": frames.get_frame_count(animation), "fps": frames.get_animation_speed(animation)}
		print("TIRRA_VISUAL_ANIMATIONS=" + JSON.stringify({"level": level, "sprite": sprite.name, "animations": inventory}))
		if frames.has_animation("default") or not frames.has_animation("down_walk") or frames.get_frame_count("down_walk") == 0:
			return "Control must exercise the real directional PCK contract without a default animation"
		for direction in ["up", "down", "left", "right"]:
			for moving in [false, true]:
				var requested: String = direction + ("_walk" if moving else "_stopped")
				var expected := requested
				if not frames.has_animation(expected) or frames.get_frame_count(expected) == 0:
					expected = "down_walk" if moving else "down_stopped"
				var count := frames.get_frame_count(expected)
				if count == 0: return "The declared directional fallback lacks frames"
				var fps := frames.get_animation_speed(expected)
				var durations := []
				for index in range(count): durations.append(frames.get_frame_duration(expected, index))
				view._update_tirra_visual(player, data, direction, moving)
				if sprite.animation != expected or not sprite.visible or sprite.frame >= count:
					return "Mounted visual did not select a valid authored directional animation"
				sprite.set_frame_and_progress(mini(1, count - 1), 0.375)
				view._update_tirra_visual(player, data, direction, moving)
				if sprite.frame != mini(1, count - 1) or not is_equal_approx(sprite.frame_progress, 0.375):
					return "Repeated authority snapshots reset the mount's animation phase"
				if frames.get_animation_speed(expected) != fps: return "Client updates changed authored animation timing"
				for index in range(count):
					if frames.get_frame_duration(expected, index) != durations[index] or frames.get_frame_texture(expected, index) == null:
						return "Client updates changed or emptied the authored animation frames"
	return true

func test_compact_egg_snapshots_reuse_the_authored_scene_and_retire_it_when_absent() -> Variant:
	view.update_game_state({"eg": {"fixture": [3, 4]}})
	var egg = view.egg_nodes.fixture
	var sprite: AnimatedSprite2D = egg.get_node("AnimatedSprite2D")
	if sprite.sprite_frames == null or not sprite.sprite_frames.has_animation(sprite.animation) \
			or sprite.sprite_frames.get_frame_count(sprite.animation) == 0:
		return "The real egg scene did not retain a valid authored sprite animation"
	var player: AnimationPlayer = egg.get_node("AnimationPlayer")
	player.seek(0.4, true)
	var phase := player.current_animation_position
	var sprite_animation := sprite.animation
	view.update_game_state({"eg": {"fixture": [4, 4]}})
	if view.egg_nodes.fixture != egg or egg.position != Vector2(4.5 * GameConfig.TILE_SIZE, 4.5 * GameConfig.TILE_SIZE) \
			or player.current_animation_position != phase or sprite.animation != sprite_animation:
		return "An egg snapshot replaced its scene or reset its authored animation phase"
	view.update_game_state({"eg": {}})
	await get_tree().process_frame
	return assert_true(view.egg_nodes.is_empty() and not is_instance_valid(egg),
		"An absent authoritative egg must retire its visual scene")

extends "res://tests/bot_test_suite.gd"

const Limits = preload("res://shared/constants.gd")
const SnapshotStats = preload("res://shared/player_snapshot_stats.gd")
var player: ServerPlayer
var pickup: ServerPowerUp

func setup_suite() -> void:
	pass

func teardown_suite() -> void:
	pass

func setup_test() -> void:
	player = ServerPlayer.new()
	pickup = ServerPowerUp.new()

func teardown_test() -> void:
	pickup.free()
	player.free()

func collect(type: int) -> void:
	pickup.powerup_type = type
	player.collect_powerup(pickup)

func test_normal_fire_retains_normal_limit() -> Variant:
	player.bomb_range = Limits.FIRE_MAX
	collect(ServerPowerUp.PowerUpType.RANGE_INCREASE)
	return assert_eq(player.bomb_range, Limits.FIRE_MAX)

func test_fire_pickup_cannot_reduce_full_fire() -> Variant:
	collect(ServerPowerUp.PowerUpType.FULL_FIRE)
	collect(ServerPowerUp.PowerUpType.RANGE_INCREASE)
	collect(ServerPowerUp.PowerUpType.FULL_FIRE)
	return assert_eq(player.bomb_range, Limits.FIRE_MAX_FULL)

func test_full_fire_does_not_corrupt_bomb_capacity_in_packet() -> Variant:
	player.max_bombs = 2
	collect(ServerPowerUp.PowerUpType.FULL_FIRE)
	var packet: Array = player.get_state_minimal()["s"]
	return assert_eq((packet[0] >> 12) & 15, 2, "Range 16 overwrote the bomb-capacity field")

func test_full_fire_state_is_per_player() -> Variant:
	collect(ServerPowerUp.PowerUpType.FULL_FIRE)
	var other := ServerPlayer.new()
	var independent: bool = not other.has_full_fire and not other.get_state()["has_full_fire"]
	other.free()
	return assert_true(independent and player.get_state()["has_full_fire"])

func test_server_packet_round_trips_full_fire_and_other_stats() -> Variant:
	player.max_bombs = 10
	player.bombs_placed = 6
	player.skate_count = 9
	player.bomb_type = 3
	player.has_bomb_kicker = true
	player.is_immortal = true
	collect(ServerPowerUp.PowerUpType.FULL_FIRE)
	var decoded: Dictionary = SnapshotStats.unpack(player.get_state_minimal()["s"])
	return assert_eq(decoded, {
		"max_bombs": 10, "bomb_range": 16, "bombs_placed": 6,
		"skate_count": 9, "bomb_type": 3,
		"flags": 1 | 128 | 512 | 1024,
	})

func test_legacy_packet_fields_keep_their_positions() -> Variant:
	return assert_eq(SnapshotStats.unpack([0x2835, (2 << 16) | 7]), {
		"max_bombs": 2, "bomb_range": 8, "bombs_placed": 3,
		"skate_count": 5, "bomb_type": 2, "flags": 7,
	})

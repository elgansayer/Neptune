extends "res://tests/bot_test_suite.gd"

const Runtime = preload("res://shared/runtime_config.gd")

func test_casual_demo_defaults_and_bounded_ci_override() -> Variant:
	var normal := Runtime.parse_arguments([], "res://main_server.tscn")
	var bounded := Runtime.parse_arguments(["--room-duration=12", "--room-countdown=1", "--room-intermission=1"], "res://main_server.tscn")
	return assert_true(normal.error.is_empty() and normal.room_duration == 180
		and normal.room_countdown == 3 and normal.room_intermission == 5
		and bounded.error.is_empty() and bounded.room_duration == 12
		and bounded.room_countdown == 1 and bounded.room_intermission == 1,
		"Production and short CI timing must remain explicit trusted server configuration")

func test_invalid_missing_duplicate_and_nonfinite_durations_fail_closed() -> Variant:
	for option in ["--room-duration", "--room-countdown", "--room-intermission"]:
		for value in ["", "0", "-1", "1.5", "nan", "inf", "abc", "99999999999999999999999999999999999999"]:
			if Runtime.parse_arguments([option + "=" + value]).error.is_empty():
				return "Invalid room timing accepted: " + option + "=" + value
		if Runtime.parse_arguments([option]).error.is_empty(): return "Missing room timing accepted"
		if Runtime.parse_arguments([option + "=1", option + "=2"]).error.is_empty(): return "Duplicate room timing accepted"
	for arguments in [["--room-duration=3601"], ["--room-countdown=31"], ["--room-intermission=61"]]:
		if Runtime.parse_arguments(arguments).error.is_empty(): return "Unbounded room timing accepted"
	return true

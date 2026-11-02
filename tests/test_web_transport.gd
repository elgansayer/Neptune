extends "res://tests/bot_test_suite.gd"

const Runtime = preload("res://shared/runtime_config.gd")

func test_native_defaults_and_browser_transport_are_explicit() -> Variant:
	var native := Runtime.parse_arguments([])
	var browser := Runtime.parse_arguments([], "", "websocket")
	var server := Runtime.parse_arguments(["--transport=websocket"], "res://main_server.tscn")
	return assert_true(native.transport == "enet" and browser.transport == "websocket"
		and server.transport == "websocket" and server.role == "server", "Transport must preserve native defaults and permit browser servers")

func test_invalid_duplicate_and_missing_transports_fail_closed() -> Variant:
	for args in [["--transport"], ["--transport="], ["--transport=http"], ["--transport=enet", "--transport=websocket"]]:
		if Runtime.parse_arguments(args).error.is_empty(): return "Invalid transport accepted: " + str(args)
	return true

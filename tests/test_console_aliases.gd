extends "res://tests/bot_test_suite.gd"

const ALIAS := "__neptune_alias_regression__"

func setup_suite() -> void:
	pass

func teardown_suite() -> void:
	pass

func setup_test() -> void:
	LimboConsole.remove_alias(ALIAS)

func teardown_test() -> void:
	LimboConsole.remove_alias(ALIAS)

func test_unknown_command_is_one_argument() -> Variant:
	return assert_eq(LimboConsole.get_alias_argv(ALIAS), PackedStringArray([ALIAS]))

func test_alias_preserves_quoted_arguments() -> Variant:
	LimboConsole.add_alias(ALIAS, 'echo "hello world"')
	return assert_eq(LimboConsole.get_alias_argv(ALIAS), PackedStringArray(["echo", '"hello world"']))

func test_returned_arguments_do_not_mutate_registered_alias() -> Variant:
	LimboConsole.add_alias(ALIAS, "echo original")
	var arguments := LimboConsole.get_alias_argv(ALIAS)
	arguments[0] = "changed"
	arguments.append("extra")
	return assert_eq(LimboConsole.get_alias_argv(ALIAS), PackedStringArray(["echo", "original"]), "Caller changed the stored alias")

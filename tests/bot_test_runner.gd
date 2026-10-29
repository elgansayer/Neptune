extends Node

## PR #18 discovery + PR #20 selection; use run_bot_tests.sh to detect engine errors.
@export var run_all_tests := true
@export var run_category := ""
@export var run_specific_test := ""
@export var exit_on_finish := true
@export var test_root := "res://tests"

var test_results := {}
var tests_passed := 0
var tests_failed := 0
var files_executed := 0
var current_test_instance: Node = null

func _ready() -> void:
	print("=== BOT TEST RUNNER STARTED ===")
	if _parse_cmdline_args():
		await get_tree().process_frame
		var scripts := find_all_test_scripts(test_root)
		var selected: Array = []
		if not run_specific_test.is_empty():
			for path in scripts:
				if path == run_specific_test or path.get_file() == run_specific_test or path.get_file().get_basename() == run_specific_test:
					selected.append(path)
			if selected.size() != 1:
				_fail("selection", "Specific selection must match exactly one file: %s (%d matches)" % [run_specific_test, selected.size()])
				selected.clear()
		elif not run_category.is_empty():
			for path in scripts:
				var relative: String = path.trim_prefix(test_root + "/")
				if relative.begins_with(run_category + "/"):
					selected.append(path)
		elif run_all_tests:
			selected = scripts
		if selected.is_empty() and tests_failed == 0:
			_fail("selection", "No test files selected")
		print("Selected %d test files" % selected.size())
		for path in selected:
			await run_test_file(path)
	print_summary()
	if exit_on_finish:
		get_tree().quit(1 if tests_failed > 0 or tests_passed == 0 else 0)

func _parse_cmdline_args() -> bool:
	for arg in OS.get_cmdline_user_args():
		if arg == "--run-all":
			run_all_tests = true
		elif arg.begins_with("--run-category="):
			run_category = arg.trim_prefix("--run-category=")
			if run_category.is_empty() or run_category.begins_with("/") or ".." in run_category.split("/"):
				_fail("arguments", "Invalid test category")
		elif arg.begins_with("--run-specific="):
			run_specific_test = arg.trim_prefix("--run-specific=")
			if run_specific_test.is_empty():
				_fail("arguments", "Empty specific selection")
		else:
			_fail("arguments", "Unknown argument: " + arg)
	if not run_category.is_empty() and not run_specific_test.is_empty():
		_fail("arguments", "Choose a category or a specific file, not both")
	return tests_failed == 0

func find_all_test_scripts(path: String = "res://tests") -> Array:
	var scripts: Array = []
	var dir := DirAccess.open(path)
	if dir == null:
		_fail(path, "Cannot open test directory")
		return scripts
	for directory in dir.get_directories():
		if directory.begins_with("."):
			continue
		if dir.is_link(directory):
			_fail(path.path_join(directory), "Symlinked test directories are unsupported")
			continue
		scripts.append_array(find_all_test_scripts(path.path_join(directory)))
	for file_name in dir.get_files():
		# Named support library, not an executable suite.
		if path.path_join(file_name) == "res://tests/test_helpers.gd":
			continue
		if file_name.ends_with(".gd") and (file_name.begins_with("test_") or file_name.ends_with("_test.gd")):
			scripts.append(path.path_join(file_name))
	scripts.sort()
	return scripts

func run_test_file(path: String) -> void:
	print("Running test file: " + path)
	files_executed += 1
	var script = load(path)
	if not script is GDScript or not script.can_instantiate():
		_fail(path, "Cannot load/instantiate test script")
		return
	var instance = script.new()
	if not instance is Node:
		_fail(path, "Test script must extend Node")
		if instance is Object and not instance is RefCounted:
			instance.free()
		return
	current_test_instance = instance
	add_child(instance)
	if instance.has_method("run_tests"):
		await instance.run_tests()
		_record_suite(path, instance)
	elif instance.has_method("execute"):
		if instance.has_method("setup"):
			await instance.setup()
		var result = await instance.execute()
		if instance.has_method("teardown"):
			await instance.teardown()
		if result is bool:
			if result:
				_pass(path)
			else:
				_fail(path, "execute() returned false")
		elif result == null and "test_result" in instance and instance.test_result is String:
			# Legacy suites require an explicit result; null alone never passes.
			if instance.test_result.begins_with("PASS:"):
				_pass(path)
			else:
				_fail(path, "Missing, inconclusive or failing explicit result: " + instance.test_result)
		else:
			_fail(path, "execute() requires a bool or explicit PASS: test_result")
	else:
		_fail(path, "Missing run_tests()/execute() contract")
	instance.queue_free()
	current_test_instance = null
	await get_tree().process_frame

func _record_suite(path: String, instance: Node) -> void:
	for property in ["passed", "failed", "results"]:
		if not property in instance:
			_fail(path, "Missing suite property: " + property)
			return
	var passed = instance.passed
	var failed = instance.failed
	var results = instance.results
	if not passed is int or not failed is int or passed < 0 or failed < 0 or not results is Dictionary:
		_fail(path, "Invalid suite counters/results")
		return
	if passed + failed == 0 or results.size() != passed + failed:
		_fail(path, "Suite must report at least one result and matching counts")
		return
	var actual_passed := 0
	var actual_failed := 0
	for name in results:
		var status = results[name]
		if not status is String or (status != "PASS" and not status.begins_with("FAIL")):
			_fail(path, "Invalid suite result: " + str(name))
			return
		if status == "PASS":
			actual_passed += 1
		else:
			actual_failed += 1
	if actual_passed != passed or actual_failed != failed:
		_fail(path, "Suite counters disagree with results")
		return
	for name in results:
		test_results[path + "::" + str(name)] = results[name]
	tests_passed += passed
	tests_failed += failed

func _pass(name: String) -> void:
	tests_passed += 1
	test_results[name] = "PASS"

func _fail(name: String, reason: String) -> void:
	tests_failed += 1
	test_results[name + "::error_%d" % tests_failed] = "FAIL: " + reason
	print("FAIL: %s: %s" % [name, reason])

func print_summary() -> void:
	print("=== BOT TEST SUMMARY ===")
	print("Total: %d | Passed: %d | Failed: %d" % [tests_passed + tests_failed, tests_passed, tests_failed])
	print("NEPTUNE_TEST_RESULT=" + JSON.stringify({
		"schema": 1, "files": files_executed, "passed": tests_passed,
		"failed": tests_failed, "results": test_results
	}))

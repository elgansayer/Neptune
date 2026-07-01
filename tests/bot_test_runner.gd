extends Node

# Bot Test Runner
# Discovers and executes bot tests

@export var run_all_tests := true
@export var run_category := ""
@export var run_specific_test := ""
@export var exit_on_finish := true

var test_results := {}
var tests_passed := 0
var tests_failed := 0
var current_test_instance: Node = null

func _ready() -> void:
	print("=== BOT TEST RUNNER STARTED ===")
	
	_parse_cmdline_args()

	# Wait a frame to let things settle
	await get_tree().process_frame
	
	if not run_specific_test.is_empty():
		await run_specific(run_specific_test)
	elif not run_category.is_empty():
		await run_category_tests(run_category)
	elif run_all_tests:
		await run_all()
	
	print_summary()
	
	if exit_on_finish:
		if tests_failed > 0:
			get_tree().quit(1)
		else:
			get_tree().quit(0)

func _parse_cmdline_args() -> void:
	var args = OS.get_cmdline_user_args()
	for arg in args:
		if arg.begins_with("--run-category="):
			run_category = arg.trim_prefix("--run-category=")
			run_all_tests = false
		elif arg.begins_with("--run-specific="):
			run_specific_test = arg.trim_prefix("--run-specific=")
			run_all_tests = false

func run_all() -> void:
	var test_scripts = find_test_scripts_recursive("res://tests")
	print("Found %d test files" % test_scripts.size())
	
	for test_path in test_scripts:
		await run_test_file(test_path)

func run_category_tests(category: String) -> void:
	print("Running tests in category: %s" % category)
	var all_scripts = find_test_scripts_recursive("res://tests")
	var category_scripts = []

	for script_path in all_scripts:
		if ("/" + category + "/") in script_path or script_path.ends_with("/" + category):
			category_scripts.append(script_path)

	print("Found %d test files in category %s" % [category_scripts.size(), category])

	for test_path in category_scripts:
		await run_test_file(test_path)

func run_specific(test_name: String) -> void:
	print("Running specific test: %s" % test_name)
	var all_scripts = find_test_scripts_recursive("res://tests")
	var target_script = ""

	for script_path in all_scripts:
		if script_path.ends_with(test_name) or script_path.ends_with(test_name + ".gd"):
			target_script = script_path
			break

	if target_script == "":
		print("Could not find test matching: %s" % test_name)
		return

	await run_test_file(target_script)

func find_test_scripts_recursive(path: String) -> Array:
	var scripts = []
	var dir = DirAccess.open(path)
	if dir:
		dir.list_dir_begin()
		var file_name = dir.get_next()
		while file_name != "":
			if file_name != "." and file_name != "..":
				var full_path = path + "/" + file_name
				if dir.current_is_dir():
					scripts.append_array(find_test_scripts_recursive(full_path))
				elif file_name.begins_with("test_") and file_name.ends_with(".gd"):
					scripts.append(full_path)
				elif file_name.ends_with("_test.gd"):
					scripts.append(full_path)
			file_name = dir.get_next()
	return scripts

func run_test_file(path: String) -> void:
	print("\nRunning test file: %s" % path)
	var script = load(path)
	if not script:
		print("Failed to load script: %s" % path)
		return
		
	var test_instance = script.new()
	if not test_instance is Node:
		print("Test script must extend Node: %s" % path)
		return
		
	add_child(test_instance)
	current_test_instance = test_instance
	
	print("Instance script: ", test_instance.get_script().resource_path)
	print("Has run_tests: ", test_instance.has_method("run_tests"))
	
	if test_instance.has_method("run_tests"):
		await test_instance.run_tests()
		tests_passed += test_instance.passed
		tests_failed += test_instance.failed
		test_results.merge(test_instance.results)
	elif test_instance.has_method("execute"):
		var result = await test_instance.execute()
		if result == true:
			tests_passed += 1
			test_results[path.get_file()] = "PASS"
		else:
			tests_failed += 1
			test_results[path.get_file()] = "FAIL"
	else:
		print("Test file does not have run_tests or execute method: %s" % path)
	
	current_test_instance.queue_free()
	current_test_instance = null
	await get_tree().process_frame

func print_summary() -> void:
	print("\n=== BOT TEST SUMMARY ===")
	print("Total: %d | Passed: %d | Failed: %d" % [
		tests_passed + tests_failed,
		tests_passed,
		tests_failed
	])
	if tests_passed + tests_failed > 0:
		print("Success Rate: %.1f%%" % (100.0 * tests_passed / (tests_passed + tests_failed)))
	
	if tests_failed > 0:
		print("\nFailed Tests:")
		for test_name in test_results:
			if test_results[test_name].begins_with("FAIL"):
				print("  - %s: %s" % [test_name, test_results[test_name]])

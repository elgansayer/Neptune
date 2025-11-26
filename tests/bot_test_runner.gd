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
	
	# Wait a frame to let things settle
	await get_tree().process_frame
	
	if run_all_tests:
		await run_all()
	elif run_category != "":
		# TODO: Implement category filtering
		print("Category filtering not yet implemented")
	elif run_specific_test != "":
		# TODO: Implement specific test running
		print("Specific test running not yet implemented")
	
	print_summary()
	
	if exit_on_finish:
		if tests_failed > 0:
			get_tree().quit(1)
		else:
			get_tree().quit(0)

func run_all() -> void:
	var test_scripts = find_all_test_scripts()
	print("Found %d test files" % test_scripts.size())
	
	for test_path in test_scripts:
		await run_test_file(test_path)

func find_all_test_scripts() -> Array:
	var scripts = []
	var dir = DirAccess.open("res://tests")
	if dir:
		dir.list_dir_begin()
		var file_name = dir.get_next()
		while file_name != "":
			if not dir.current_is_dir():
				if file_name.ends_with("_test.gd"):
					scripts.append("res://tests/" + file_name)
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
	else:
		print("Test file does not have run_tests method: %s" % path)
	
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

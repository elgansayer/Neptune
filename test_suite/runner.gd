extends Node

# Simple test runner that loads and runs tests under res://test_suite/tests
# Usage (via CLI): godot --headless --fixed-fps 60 --disable-render-loop --path . res://test_suite/runner.tscn -- --seed=12345 --verbose

var verbose: bool = false
var seed: int = 12345

var results := {
	"total": 0,
	"passed": 0,
	"failed": 0,
	"failures": []
}

var assert_util
var tick_util
var map_factory
var ai_spawn

func _ready():
	_parse_args()
	_init_helpers()
	print("[Runner] Starting tests. Seed=", seed, " Verbose=", verbose)
	_run_all_tests()

func _parse_args():
	for arg in OS.get_cmdline_args():
		if arg.begins_with("--seed="):
			seed = int(arg.trim_prefix("--seed="))
		elif arg == "--verbose":
			verbose = true

func _init_helpers():
	assert_util = load("res://test_suite/helpers/test_assert.gd").new()
	tick_util = load("res://test_suite/helpers/tick_util.gd").new()
	map_factory = load("res://test_suite/helpers/map_factory.gd").new()
	ai_spawn = load("res://test_suite/helpers/ai_spawn.gd").new()
	add_child(tick_util)
	add_child(ai_spawn)  # Add to tree so it can access get_tree()
	# Seed RNG deterministically
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	Engine.set_meta("test_rng", rng)

func _run_all_tests():
	var test_dir := "res://test_suite/tests"
	var files := []
	var da := DirAccess.open(test_dir)
	if da:
		da.list_dir_begin()
		var f = da.get_next()
		while f != "":
			if not da.current_is_dir() and f.ends_with(".gd"):
				files.append(f)
			f = da.get_next()
		da.list_dir_end()
	else:
		printerr("[Runner] Test directory not found: ", test_dir)
		_results_and_exit()
		return

	files.sort()  # predictable order

	for file in files:
		var path = test_dir + "/" + file
		print("[Runner] Running ", path)
		var test_script = load(path)
		if not test_script:
			_record_failure(file, "Failed to load script")
			continue
		var test_node = test_script.new()
		add_child(test_node)
		await get_tree().process_frame
		results.total += 1
		var ok := false
		var message := ""
		# Each test must implement: func run(ctx) -> Dictionary {ok: bool, message: String}
		if test_node.has_method("run"):
			var ctx = {
				"assert": assert_util,
				"tick": tick_util,
				"map_factory": map_factory,
				"ai_spawn": ai_spawn,
				"verbose": verbose
			}
			var outcome = await test_node.run(ctx)
			ok = bool(outcome.get("ok", false))
			message = String(outcome.get("message", ""))
		else:
			message = "No run() method"

		if ok:
			results.passed += 1
			print("[PASS] ", file)
		else:
			_record_failure(file, message)
		remove_child(test_node)
		test_node.queue_free()

	_results_and_exit()

func _record_failure(name: String, message: String):
	results.failed += 1
	results.failures.append({"name": name, "message": message})
	printerr("[FAIL] ", name, ": ", message)

func _results_and_exit():
	print("[RESULTS] total=", results.total, " passed=", results.passed, " failed=", results.failed)
	if results.failed > 0:
		for f in results.failures:
			printerr("[FAILURE] ", f.name, ": ", f.message)
		get_tree().quit(1)
	else:
		print("All tests passed.")
		get_tree().quit(0)

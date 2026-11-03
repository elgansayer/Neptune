extends "res://tests/bot_test_suite.gd"

const TimedPathfinder = preload("res://shared/ai/pathfinding/danger_aware_astar.gd")
var route: DangerAwareAStar

func setup_suite() -> void:
	pass

func teardown_suite() -> void:
	pass

func setup_test() -> void:
	route = TimedPathfinder.new()
	route.region = Rect2i(0, 0, 5, 3)
	route.cell_size = Vector2(16, 16)
	route.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_NEVER
	route.update()
	route.path_start_time_msec = 1000.0
	route.bot_speed_msec_per_tile = 200.0
	# A three-cell wall forces six moves although Manhattan distance is four.
	for x in range(1, 4):
		route.set_point_solid(Vector2i(x, 1), true)

func teardown_test() -> void:
	route = null

func test_actual_detour_arrival_rejects_optimistic_manhattan_deadline() -> Variant:
	route.threat_matrix_ref = {"4,1": 2100.0}
	var path := route.get_timed_id_path(Vector2i(0, 1), Vector2i(4, 1))
	return assert_true(path.is_empty(), "Six moves arrive at 2200ms; a four-move Manhattan estimate wrongly accepts the 2100ms deadline")

func test_later_deadline_allows_same_detour_without_changing_grid() -> Variant:
	route.threat_matrix_ref = {"4,1": 2400.0}
	var before := route.threat_matrix_ref.duplicate()
	var path := route.get_timed_id_path(Vector2i(0, 1), Vector2i(4, 1))
	return assert_true(path.size() == 7 and path.front() == Vector2i(0, 1) and path.back() == Vector2i(4, 1) and route.threat_matrix_ref == before and route.is_point_solid(Vector2i(2, 1)), "Expected six traversed edges with unchanged forecast and solids")

func test_current_flame_forces_safe_alternative_route() -> Variant:
	route.threat_matrix_ref = {"2,0": 1000.0}
	var path := route.get_timed_id_path(Vector2i(0, 1), Vector2i(4, 1))
	return assert_true(path.size() == 7 and path.has(Vector2i(2, 2)) and not path.has(Vector2i(2, 0)), "Native route must use the lower corridor around active fire")

func test_source_departure_must_precede_deadline() -> Variant:
	# The upper corridor's first cell is safe to enter at 1200ms, but becomes
	# lethal before the actor can leave it at 1400ms plus 100ms clearance.
	route.threat_matrix_ref = {"0,0": 1450.0}
	var path := route.get_timed_id_path(Vector2i(0, 1), Vector2i(4, 1))
	return assert_true(not path.is_empty() and not path.has(Vector2i(0, 0)), "Arrival-only checks route through a tile that ignites during departure")

func test_boundary_deadline_is_rejected() -> Variant:
	route.threat_matrix_ref = {"4,1": 2300.0}
	return assert_true(route.get_timed_id_path(Vector2i(0, 1), Vector2i(4, 1)).is_empty(), "Arrival plus the 100ms clearance must be strictly before lethality")

func test_real_path_length_enforces_explicit_search_budget() -> Variant:
	if not route.get_timed_id_path(Vector2i(0, 1), Vector2i(4, 1), 5).is_empty():
		return "Five-step budget accepted a six-step detour"
	return assert_eq(route.get_timed_id_path(Vector2i(0, 1), Vector2i(4, 1), 6).size(), 7)

func test_actor_speed_changes_route_feasibility() -> Variant:
	route.threat_matrix_ref = {"4,1": 2400.0}
	var normal := route.get_timed_id_path(Vector2i(0, 1), Vector2i(4, 1))
	route.bot_speed_msec_per_tile = 400.0
	return assert_true(not normal.is_empty() and route.get_timed_id_path(Vector2i(0, 1), Vector2i(4, 1)).is_empty(), "Slower actors must not inherit the faster actor's feasible route")

func test_vector_deadlines_and_invalid_speed_fail_closed() -> Variant:
	route.threat_matrix_ref = {Vector2i(4, 1): 1000.0}
	if not route.get_timed_id_path(Vector2i(0, 1), Vector2i(4, 1)).is_empty():
		return "Vector-key forecast was ignored"
	route.threat_matrix_ref.clear()
	route.bot_speed_msec_per_tile = 0.0
	return assert_true(route.get_timed_id_path(Vector2i(0, 1), Vector2i(4, 1)).is_empty(), "Invalid movement speed must not produce a route")

func _interval_corridor() -> void:
	route.region = Rect2i(0, 0, 3, 1)
	route.update()
	route.use_hazard_intervals = true
	route.path_start_time_msec = 1000.0
	route.hazard_intervals_ref = {"1,0": [Vector2(1000.0, 1500.0)]}

func test_interval_planner_waits_for_inclusive_flame_expiry() -> Variant:
	_interval_corridor()
	var planned := route.get_timed_route(Vector2i.ZERO, Vector2i(2, 0))
	return assert_true(planned.status == "found" and planned.cells.size() == 3
		and planned.departures[1] > 1600.0 and planned.arrivals[1] > 1800.0,
		"Cannot enter a burning cell before expiry plus clearance; route must carry an explicit wait")

func test_interval_wait_is_rejected_when_source_ignites_before_departure() -> Variant:
	_interval_corridor()
	route.hazard_intervals_ref["0,0"] = [Vector2(1700.0, INF)]
	return assert_eq(route.get_timed_route(Vector2i.ZERO, Vector2i(2, 0)).status, "unreachable", "Source must remain clear throughout waiting AND crossing")

func test_separate_blast_windows_do_not_become_one_permanent_deadline() -> Variant:
	_interval_corridor()
	route.hazard_intervals_ref["1,0"] = [Vector2(900.0, 1100.0), Vector2(2300.0, 2600.0)]
	var planned := route.get_timed_route(Vector2i.ZERO, Vector2i(2, 0))
	return assert_true(planned.status == "found" and planned.arrivals[2] < 2200.0, "A safe gap between two blasts must remain traversable")

func test_overlapping_flame_windows_wait_for_the_last_expiry() -> Variant:
	_interval_corridor()
	route.hazard_intervals_ref["1,0"] = [Vector2(900.0, 1400.0), Vector2(1300.0, 1900.0)]
	var planned := route.get_timed_route(Vector2i.ZERO, Vector2i(2, 0))
	return assert_true(planned.status == "found" and planned.departures[1] > 2000.0, "Overlapping fire cannot create a fictitious safe interval")

func test_interval_search_reports_expansion_budget_exhaustion() -> Variant:
	_interval_corridor()
	route.max_expansions = 1
	var planned := route.get_timed_route(Vector2i.ZERO, Vector2i(2, 0))
	return assert_true(planned.status == "exhausted" and planned.expanded == 1 and planned.cells.is_empty(), "Budget exhaustion must not masquerade as a safe route")

func test_interval_search_horizon_prevents_unbounded_waiting() -> Variant:
	_interval_corridor()
	route.hazard_intervals_ref["1,0"] = [Vector2(900.0, 1000000.0)]
	return assert_eq(route.get_timed_route(Vector2i.ZERO, Vector2i(2, 0)).status, "unreachable")

func test_interval_departure_preserves_deterministic_route_and_schedule() -> Variant:
	_interval_corridor()
	var first := route.get_timed_route(Vector2i.ZERO, Vector2i(2, 0))
	return assert_eq(route.get_timed_route(Vector2i.ZERO, Vector2i(2, 0)), first, "Same public intervals must produce the same cells, timing and work count")

func test_malformed_interval_is_not_interpreted_as_safe() -> Variant:
	_interval_corridor()
	route.hazard_intervals_ref["1,0"] = [Vector2(1500.0, 1200.0)]
	return assert_eq(route.get_timed_route(Vector2i.ZERO, Vector2i(2, 0)).status, "unreachable")

func test_cannot_wait_policy_never_schedules_a_stationary_hold() -> Variant:
	_interval_corridor()
	route.allow_wait = false
	return assert_eq(route.get_timed_route(Vector2i.ZERO, Vector2i(2, 0)).status, "unreachable", "Unstoppable movement cannot safely execute a planned stationary wait")

func test_first_edge_uses_actual_off_center_position_before_accepting_a_deadline() -> Variant:
	route.region = Rect2i(0, 0, 3, 1)
	route.update()
	route.threat_matrix_ref = {"2,0": 1560.0}
	if route.get_timed_id_path(Vector2i.ZERO, Vector2i(2, 0)).is_empty():
		return "Centered control should arrive at 1400 ms before the 1560 ms deadline and 100 ms margin"
	route.use_start_world_position = true
	route.start_world_position = Vector2(1.0, 8.0)
	return assert_true(route.get_timed_id_path(Vector2i.ZERO, Vector2i(2, 0)).is_empty(), "The real first edge is 23 px, so arrival at 1487.5 ms plus the 100 ms margin misses the deadline; assuming 16 px is unsafe")

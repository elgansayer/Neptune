extends Node

var failures: Array = []

func assert_true(cond: bool, msg: String):
	if not cond:
		failures.append(msg)

func assert_equal(a, b, msg: String):
	if a != b:
		failures.append(msg + " (" + str(a) + " != " + str(b) + ")")

func assert_not_equal(a, b, msg: String):
	if a == b:
		failures.append(msg + " (both=" + str(a) + ")")

func summary() -> Dictionary:
	return {"failed": failures.size(), "failures": failures}

func clear():
	failures.clear()

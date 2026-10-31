extends Node

# Exercise the vendored native library, including bindings and real query results.
func execute() -> bool:
	var database := SQLite.new()
	database.path = ":memory:"
	database.default_extension = ""
	database.verbosity_level = 0
	if not database.open_db():
		return false
	var payload := "quote ' and unicode Ω; DROP TABLE upgrade_probe; --"
	var valid := database.query("CREATE TABLE upgrade_probe (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
	valid = valid and database.query_with_bindings("INSERT INTO upgrade_probe (payload) VALUES (?)", [payload])
	valid = valid and database.query_with_bindings("SELECT id, payload FROM upgrade_probe WHERE payload = ?", [payload])
	var rows: Array = database.query_result
	valid = valid and rows.size() == 1 and rows[0].id == 1 and rows[0].payload == payload
	valid = valid and database.query("SELECT COUNT(*) AS total FROM upgrade_probe")
	rows = database.query_result
	valid = valid and rows.size() == 1 and rows[0].total == 1
	var closed := database.close_db()
	return valid and closed

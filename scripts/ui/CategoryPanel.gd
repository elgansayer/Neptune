extends PanelContainer

const StatEntry = preload("res://scenes/ui/StatEntry.tscn")

@onready var title_button = %TitleButton
@onready var grid = %StatsGrid

func _ready():
    title_button.pressed.connect(_on_title_button_pressed)

func set_category(category_title: String, stats: Dictionary):
    title_button.text = category_title
    # Clear previous entries
    for child in grid.get_children():
        child.queue_free()
    
    for stat_name in stats:
        var stat_value = stats[stat_name]
        var stat_entry = StatEntry.instantiate()
        grid.add_child(stat_entry)
        stat_entry.set_stat(stat_name, stat_value)

func _on_title_button_pressed():
    grid.visible = not grid.visible
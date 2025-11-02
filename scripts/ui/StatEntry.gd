extends HBoxContainer

func set_stat(stat_name: String, stat_value):
    %StatName.text = stat_name
    %StatValue.text = str(stat_value)

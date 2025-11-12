"""gdscript
class_name BaseAIController

extends Node

# Common properties and methods for all AI controllers
var personality_weights: Dictionary = {}
var current_target_tile: Vector2i = Vector2i(-1, -1)

func _init():
    # Initialize default values
    pass

func update(delta):
    # Main update function to be overridden by subclasses
    pass

func get_action():
    # Returns the next action based on AI logic
    return null
"""
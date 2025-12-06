extends Area2D

## Legacy item script - base class for all item types
## Note: The main game uses client/ui/powerup_renderer.gd and shared/server_powerup.gd instead
## This file is kept for compatibility with legacy scenes

@export_enum("power", "power_glove", "bomb", "bomb_kicker", "rollerskate", "virus", "egg") var item_type: String = "power"
@export_enum("pickup_special", "pickup", "pickup_powerglove", "got_virus", "pickup_egg") var pickup_sound: String = "pickup"

var picked = false
var correct_sound


func _ready():
	if has_node("AnimatedSprite2D"):
		$AnimatedSprite2D.play(item_type)

	var sound_path = "res://res/sounds/items/" + pickup_sound + ".ogg"
	if ResourceLoader.exists(sound_path):
		correct_sound = load(sound_path)


func _on_Timer_timeout():
	if has_node("AnimationPlayer"):
		$AnimationPlayer.play("spin")


func play_sound():
	if has_node("AudioStreamPlayer2D") and correct_sound:
		if !$AudioStreamPlayer2D.is_playing():
			$AudioStreamPlayer2D.stream = correct_sound
			$AudioStreamPlayer2D.play()


func award_player(_player):
	print("award_player item")


func _on_Node2D_body_entered(body: Node):
	if picked:
		return

	if body.is_in_group("players") or body.name.begins_with("Player"):
		picked_up(body)

func dizzy():
	queue_free()
	
func picked_up(player):
	picked = true
	if has_node("Timer"):
		$Timer.stop()

	play_sound()
	call_deferred("award_player", player)
	if has_node("AnimationPlayer"):
		# Defer all animation operations to avoid physics callback issues
		$AnimationPlayer.call_deferred("stop")
		$AnimationPlayer.call_deferred("play", "picked_up")
	# Also defer disabling the collision shape to prevent physics errors
	if has_node("CollisionShape2D"):
		$CollisionShape2D.set_deferred("disabled", true)


func explode():
	picked = true
	if has_node("Timer"):
		$Timer.stop()
	if has_node("AnimationPlayer"):
		$AnimationPlayer.play("explode")

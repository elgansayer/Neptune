extends Node

## GridHelpers - Utility functions for grid-based positioning
## Replaces SBomberman's world singleton grid helpers

## Convert grid coordinates to centered pixel position
static func grid_to_pixel(grid_pos: Vector2i) -> Vector2:
	var tile_size = GameConfig.TILE_SIZE
	return Vector2(
		grid_pos.x * tile_size + tile_size / 2.0,
		grid_pos.y * tile_size + tile_size / 2.0
	)

## Convert pixel position to grid coordinates
static func pixel_to_grid(pixel_pos: Vector2) -> Vector2i:
	var tile_size = GameConfig.TILE_SIZE
	return Vector2i(
		int(pixel_pos.x / tile_size),
		int(pixel_pos.y / tile_size)
	)

## Get the center position of a grid cell
static func get_center_position_from_grid(grid_pos: Vector2i) -> Vector2:
	return grid_to_pixel(grid_pos)

## Check if grid position is within map bounds
static func is_valid_grid_position(grid_pos: Vector2i) -> bool:
	return (grid_pos.x >= 0 and grid_pos.x < GameConfig.map_width and
			grid_pos.y >= 0 and grid_pos.y < GameConfig.map_height)

## Get neighboring grid positions in 4 directions (up, down, left, right)
static func get_neighbors(grid_pos: Vector2i) -> Array[Vector2i]:
	var neighbors: Array[Vector2i] = []
	neighbors.append(Vector2i(grid_pos.x, grid_pos.y - 1))  # Up
	neighbors.append(Vector2i(grid_pos.x, grid_pos.y + 1))  # Down
	neighbors.append(Vector2i(grid_pos.x - 1, grid_pos.y))  # Left
	neighbors.append(Vector2i(grid_pos.x + 1, grid_pos.y))  # Right
	return neighbors

## Get directional offset for explosion expansion
static func get_direction_offset(direction: int) -> Vector2i:
	match direction:
		0:  # Up
			return Vector2i(0, -1)
		1:  # Down
			return Vector2i(0, 1)
		2:  # Left
			return Vector2i(-1, 0)
		3:  # Right
			return Vector2i(1, 0)
		_:
			return Vector2i(0, 0)

## Snap a pixel position to the nearest grid center
static func snap_to_grid_center(pixel_pos: Vector2) -> Vector2:
	var grid_pos = pixel_to_grid(pixel_pos)
	return get_center_position_from_grid(grid_pos)

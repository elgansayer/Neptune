extends Node2D
class_name MapMetadata

## Map Metadata for Stage 1 - Saturn Bomberman Classic
## This script provides map information that the game server reads

# === MAP INFORMATION ===
var map_name: String = "Saturn Stage 1"
var map_id: String = "saturn_classic_stage1"
var author: String = "Elgan"
var description: String = "Classic Saturn Bomberman Stage 1 arena with traditional grid layout"
var version: String = "1.0"
var theme: String = "classic"

# === MAP DIMENSIONS ===
# These should match your TileMap dimensions
var map_width: int = 21  # tiles
var map_height: int = 14  # tiles
var tile_size: int = 16  # pixels

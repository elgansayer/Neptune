extends Control

# LEGACY: This UI uses NakamaService which is not currently integrated
# Check if NakamaService singleton exists to prevent errors
const HAS_NAKAMA = false  # Set to true when NakamaService is re-integrated

# Header Nodes
@onready var display_name_edit = $VBoxContainer/Header/HBoxContainer/DisplayName
@onready var nakama_status_label = $VBoxContainer/Header/HBoxContainer/NakamaStatus
@onready var login_button = $VBoxContainer/Header/HBoxContainer/LoginButton
@onready var back_button = $VBoxContainer/Header/HBoxContainer/BackButton
@onready var save_button = $VBoxContainer/Header/HBoxContainer/SaveButton

# Character Selector Nodes
@onready var character_grid = $VBoxContainer/CharacterSelector/ScrollContainer/CharacterGrid

# Stats Section Nodes
@onready var core_gameplay_stats_panel = $VBoxContainer/StatsSection/VBoxContainer/CoreGameplayStats
@onready var power_up_stats_panel = $VBoxContainer/StatsSection/VBoxContainer/PowerUpStats
@onready var skill_and_efficiency_panel = $VBoxContainer/StatsSection/VBoxContainer/SkillAndEfficiency
@onready var combat_behavior_panel = $VBoxContainer/StatsSection/VBoxContainer/CombatBehavior
@onready var ranking_and_achievements_panel = $VBoxContainer/StatsSection/VBoxContainer/RankingAndAchievements
@onready var map_and_mode_stats_panel = $VBoxContainer/StatsSection/VBoxContainer/MapAndModeStats
@onready var team_play_stats_panel = $VBoxContainer/StatsSection/VBoxContainer/TeamPlayStats
@onready var progression_stats_panel = $VBoxContainer/StatsSection/VBoxContainer/ProgressionStats
@onready var style_and_customization_panel = $VBoxContainer/StatsSection/VBoxContainer/StyleAndCustomization
@onready var meta_behavioral_stats_panel = $VBoxContainer/StatsSection/VBoxContainer/MetaBehavioralStats
@onready var advanced_analytics_panel = $VBoxContainer/StatsSection/VBoxContainer/AdvancedAnalytics
@onready var fun_cosmetic_stats_panel = $VBoxContainer/StatsSection/VBoxContainer/FunCosmeticStats

# Placeholder for player stats
var player_stats = {
    "Core Gameplay Stats": {
        "Matches Played": 124,
        "Matches Won": 78,
        "Matches Lost": 46,
        "Win Rate (%)": 62.9,
        "Average Match Length": "5m 32s",
        "Fastest Win": "1m 12s",
        "Longest Survival Time": "8m 45s",
        "Average Placement": 2.3,
        "Rounds Played": 496,
        "Rounds Won": 312,
        "Round Win Rate (%)": 62.9,
        "Average Rounds per Match": 4,
        "Total Bombs Placed": 2034,
        "Bombs Placed per Match": 16.4,
        "Bombs Detonated by Player": 1800,
        "Bombs That Killed Player (self-KOs)": 23,
        "Total Kills": 412,
        "Kills per Match": 3.3,
        "Multi-Kills (2+)": 50,
        "Total Deaths": 367,
        "Deaths by Own Bombs": 23,
        "Deaths by Opponent Bombs": 300
    },
    "Power-Up Stats": {
        "Total Power-Ups Collected": 543,
        "Most Collected Power-Up": "Speed",
        "Fire Power-Ups": 123,
        "Bomb Power-Ups": 111,
        "Speed Power-Ups": 150,
        "Remote Bombs": 20,
        "Kick Power-Ups": 50,
        "Punch Power-Ups": 45,
        "Glove Power-Ups": 34
    },
    "Skill & Efficiency": {
        "Bomb Placement Accuracy": 20.2,
        "Kills Without Power-Ups": 30,
        "Bombs per Kill Ratio": 4.9,
        "Damage Dealt": 41200
    },
    "Combat Behavior": {
        "Offensive Bombs Placed": 1500,
        "Defensive Bombs Placed": 534,
        "Bomb Explosions Dodged": 1000
    },
    "Ranking & Achievements": {
        "Current Rank": "Gold 3",
        "MMR": 1540,
        "Highest Rank": "Platinum 1",
        "Longest Win Streak": 12,
        "Flawless Wins": 10
    },
    "Map & Mode Stats": {
        "Favorite Map": "Classic",
        "Win Rate on Favorite Map": 70.0,
        "Favorite Game Mode": "Free-for-All",
        "Win Rate in Favorite Mode": 65.0
    },
    "Team Play Stats": {
        "Team Matches Played": 20,
        "Team Wins": 15,
        "Team Win Rate": 75.0,
        "Assists": 30
    },
    "Progression Stats": {
        "Level": 54,
        "Total Play Time": "48h 12m",
        "XP Earned": 123456
    },
    "Style & Customization": {
        "Favorite Character": "Blue Bomber",
        "Most Used Emote": "Thumbs Up"
    },
    "Meta / Behavioral Stats": {
        "Disconnects": 5,
        "Ping Average": "45ms"
    },
    "Advanced Analytics": {
        "Kill-to-Death Ratio": 1.12,
        "Kill Participation Rate": "N/A"
    },
    "Fun / Cosmetic Stats": {
        "Total Blocks Destroyed": 10000,
        "Lucky Escapes": 5
    }
}

var character_data = {}
var selected_character_name = ""

func _ready():
    populate_stats()
    _load_character_data()
    _populate_character_grid()

    login_button.pressed.connect(_on_login_button_pressed)
    save_button.pressed.connect(_on_save_button_pressed)
    back_button.pressed.connect(_on_back_button_pressed)

    _update_ui_from_session()

func _update_ui_from_session():
    if not HAS_NAKAMA:
        nakama_status_label.text = "Nakama Disabled"
        login_button.disabled = true
        return
    
    # Original Nakama code (disabled)
    #if NakamaService.session and not NakamaService.session.is_expired():
    #    nakama_status_label.text = "Logged In"
    #    login_button.text = "Logout"
    #    display_name_edit.text = NakamaService.session.username
    #else:
    #    nakama_status_label.text = "Not Logged In"
    #    login_button.text = "Login"

func _on_login_button_pressed():
    if not HAS_NAKAMA:
        return
    
    # Original Nakama code (disabled)
    #if NakamaService.session and not NakamaService.session.is_expired():
    #    # Logout
    #    NakamaService.session = null
    #    _update_ui_from_session()
    #else:
    #    # Login (this is a placeholder for your actual login flow)
    #    var session = await NakamaService.authenticate_device("my_device_id")
    #    if session:
    #        NakamaService.session = session
    #        _update_ui_from_session()

func _on_save_button_pressed():
    if not HAS_NAKAMA:
        print("Nakama integration disabled - cannot save to server")
        return
    
    # Original Nakama code (disabled)
    #if NakamaService.session and not NakamaService.session.is_expired():
    #    var account_update = {
    #        "display_name": display_name_edit.text,
    #        "username": display_name_edit.text,
    #        "metadata": {
    #            "character": selected_character_name
    #        }
    #    }
    #    var result = await NakamaService.nakama_client.update_account(NakamaService.session, account_update)
    #    if result.is_exception():
    #        print("Error updating account: %s" % result.get_exception().message)
    #    else:
    #        print("Account updated successfully")

func _on_back_button_pressed():
    get_tree().change_scene_to_file("res://Main.tscn")

func _load_character_data():
    var dir = DirAccess.open("res://characters")
    if dir:
        dir.list_dir_begin()
        var file_name = dir.get_next()
        while file_name != "":
            if not dir.current_is_dir() and file_name.ends_with(".tscn"):
                var character_name = file_name.get_basename()
                character_data[character_name] = {
                    "name": character_name.capitalize(),
                    "scene_path": "res://characters/" + file_name,
                    "portrait": "res://characters/portraits/" + character_name.to_lower() + "_idle.png"
                }
            file_name = dir.get_next()

func _populate_character_grid():
    for char_name in character_data:
        var data = character_data[char_name]
        var button = TextureButton.new()
        button.texture_normal = load(data.portrait)
        button.custom_minimum_size = Vector2(64, 64)
        button.expand_mode = 1
        button.pressed.connect(_on_character_selected.bind(char_name))
        character_grid.add_child(button)

func _on_character_selected(character_name):
    selected_character_name = character_name
    var data = character_data[character_name]
    $VBoxContainer/Header/HBoxContainer/Avatar.texture = load(data.portrait)

func populate_stats():
    core_gameplay_stats_panel.set_category("Core Gameplay Stats", player_stats["Core Gameplay Stats"])
    power_up_stats_panel.set_category("Power-Up Stats", player_stats["Power-Up Stats"])
    skill_and_efficiency_panel.set_category("Skill & Efficiency", player_stats["Skill & Efficiency"])
    combat_behavior_panel.set_category("Combat Behavior", player_stats["Combat Behavior"])
    ranking_and_achievements_panel.set_category("Ranking & Achievements", player_stats["Ranking & Achievements"])
    map_and_mode_stats_panel.set_category("Map & Mode Stats", player_stats["Map & Mode Stats"])
    team_play_stats_panel.set_category("Team Play Stats", player_stats["Team Play Stats"])
    progression_stats_panel.set_category("Progression Stats", player_stats["Progression Stats"])
    style_and_customization_panel.set_category("Style & Customization", player_stats["Style & Customization"])
    meta_behavioral_stats_panel.set_category("Meta / Behavioral Stats", player_stats["Meta / Behavioral Stats"])
    advanced_analytics_panel.set_category("Advanced Analytics", player_stats["Advanced Analytics"])
    fun_cosmetic_stats_panel.set_category("Fun / Cosmetic Stats", player_stats["Fun / Cosmetic Stats"])


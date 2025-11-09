#!/usr/bin/env python3
"""
AI Testing and Analysis Tool
Helps test the improved AI system and analyze player logs
"""

import json
import csv
import sys
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

class AITestAnalyzer:
    def __init__(self, logs_dir: str = None):
        if logs_dir is None:
            # Default Godot user data path
            home = Path.home()
            self.logs_dir = home / ".local/share/godot/app_userdata/Bomberman/player_logs"
        else:
            self.logs_dir = Path(logs_dir)
    
    def list_sessions(self) -> List[Path]:
        """List all available log sessions"""
        if not self.logs_dir.exists():
            print(f"❌ Logs directory not found: {self.logs_dir}")
            return []
        
        sessions = list(self.logs_dir.glob("session_*.json"))
        return sorted(sessions)
    
    def analyze_session(self, session_file: Path) -> Dict:
        """Analyze a single session log"""
        with open(session_file, 'r') as f:
            data = json.load(f)
        
        stats = {
            "session_id": data["session_id"],
            "timestamp": data["timestamp"],
            "total_frames": data["total_frames"],
            "tracked_players": data["tracked_players"],
            "actions": defaultdict(int),
            "avg_danger": 0.0,
            "emergency_escapes": 0,
            "bombs_placed": 0,
            "deaths": 0,
            "kills": 0
        }
        
        # Analyze frame data
        total_danger = 0.0
        frame_count = 0
        
        for entry in data["data"]:
            if "action" in entry:
                stats["actions"][entry["action"]] += 1
                
                if entry["action"] == "PLACE_BOMB":
                    stats["bombs_placed"] += 1
                elif entry["action"] == "DIED":
                    stats["deaths"] += 1
            
            if "context" in entry:
                danger = entry["context"].get("danger_level", 0.0)
                total_danger += danger
                frame_count += 1
                
                if danger > 0.8 and entry.get("action") in ["MOVE_UP", "MOVE_DOWN", "MOVE_LEFT", "MOVE_RIGHT"]:
                    stats["emergency_escapes"] += 1
        
        if frame_count > 0:
            stats["avg_danger"] = total_danger / frame_count
        
        return stats
    
    def print_session_report(self, stats: Dict):
        """Print a formatted report of session statistics"""
        print("\n" + "="*60)
        print(f"📊 Session Report: {stats['session_id']}")
        print("="*60)
        print(f"🕐 Timestamp: {stats['timestamp']}")
        print(f"📹 Total Frames: {stats['total_frames']}")
        print(f"👥 Tracked Players: {', '.join(stats['tracked_players'])}")
        print(f"\n📈 Statistics:")
        print(f"  💣 Bombs Placed: {stats['bombs_placed']}")
        print(f"  💀 Deaths: {stats['deaths']}")
        print(f"  ⚠️  Avg Danger Level: {stats['avg_danger']:.3f}")
        print(f"  🚨 Emergency Escapes: {stats['emergency_escapes']}")
        
        print(f"\n🎮 Action Distribution:")
        total_actions = sum(stats['actions'].values())
        for action, count in sorted(stats['actions'].items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_actions * 100) if total_actions > 0 else 0
            print(f"  {action:20s}: {count:5d} ({percentage:5.1f}%)")
        print("="*60)
    
    def compare_ai_behaviors(self, session_files: List[Path]):
        """Compare behaviors across multiple sessions"""
        print("\n" + "="*60)
        print("🔬 AI Behavior Comparison")
        print("="*60)
        
        all_stats = []
        for session_file in session_files:
            stats = self.analyze_session(session_file)
            all_stats.append(stats)
        
        # Calculate averages
        avg_bombs = sum(s['bombs_placed'] for s in all_stats) / len(all_stats)
        avg_deaths = sum(s['deaths'] for s in all_stats) / len(all_stats)
        avg_danger = sum(s['avg_danger'] for s in all_stats) / len(all_stats)
        avg_escapes = sum(s['emergency_escapes'] for s in all_stats) / len(all_stats)
        
        print(f"\n📊 Averages across {len(all_stats)} sessions:")
        print(f"  💣 Bombs per session: {avg_bombs:.1f}")
        print(f"  💀 Deaths per session: {avg_deaths:.1f}")
        print(f"  ⚠️  Danger level: {avg_danger:.3f}")
        print(f"  🚨 Emergency escapes: {avg_escapes:.1f}")
        
        # Most common actions
        action_totals = defaultdict(int)
        for stats in all_stats:
            for action, count in stats['actions'].items():
                action_totals[action] += count
        
        print(f"\n🎮 Most Common Actions:")
        for action, count in sorted(action_totals.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {action:20s}: {count:5d}")
        
        print("="*60)
    
    def export_training_data(self, session_files: List[Path], output_file: str = "training_data.csv"):
        """Export consolidated training data from multiple sessions"""
        output_path = Path(output_file)
        
        print(f"\n📦 Exporting training data to {output_path}...")
        
        with open(output_path, 'w', newline='') as csvfile:
            fieldnames = [
                'session', 'time', 'frame', 'player_id',
                'pos_x', 'pos_y', 'tile_x', 'tile_y',
                'vel_x', 'vel_y', 'vel_mag',
                'action', 'danger', 'time_until_explosion',
                'escape_routes', 'nearby_bombs', 'nearby_blocks',
                'can_place_bomb', 'bomb_count'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            total_rows = 0
            for session_file in session_files:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                
                for entry in data["data"]:
                    if "position" not in entry:
                        continue
                    
                    row = {
                        'session': data['session_id'],
                        'time': entry.get('time', 0.0),
                        'frame': entry.get('frame', 0),
                        'player_id': entry.get('player_id', ''),
                        'pos_x': entry['position']['x'],
                        'pos_y': entry['position']['y'],
                        'tile_x': entry['tile']['x'],
                        'tile_y': entry['tile']['y'],
                        'vel_x': entry['velocity']['x'],
                        'vel_y': entry['velocity']['y'],
                        'vel_mag': entry['velocity']['magnitude'],
                        'action': entry.get('action', 'IDLE'),
                        'danger': entry['context'].get('danger_level', 0.0),
                        'time_until_explosion': min(entry['context'].get('time_until_explosion', 999.0), 999.0),
                        'escape_routes': entry['context'].get('escape_routes', 0),
                        'nearby_bombs': sum(1 for e in entry['context'].get('nearby_entities', []) if e['type'] == 'bomb'),
                        'nearby_blocks': sum(1 for e in entry['context'].get('nearby_entities', []) if e['type'] == 'soft_block'),
                        'can_place_bomb': 1 if entry['context'].get('can_place_bomb', False) else 0,
                        'bomb_count': entry['context'].get('bomb_count', 0)
                    }
                    writer.writerow(row)
                    total_rows += 1
            
            print(f"✅ Exported {total_rows} training samples")
            print(f"📁 File: {output_path.absolute()}")

def main():
    analyzer = AITestAnalyzer()
    
    print("🤖 AI Testing and Analysis Tool")
    print("="*60)
    
    # List available sessions
    sessions = analyzer.list_sessions()
    
    if not sessions:
        print("❌ No log sessions found.")
        print(f"💡 Logs should be in: {analyzer.logs_dir}")
        print("\nTo enable logging, add this to game_instance.gd:")
        print("""
var player_logger = PlayerLogManager.new(self)
player_logger.start_session()
# ... in _process:
player_logger.update(delta)
# ... on match end:
player_logger.end_session()
        """)
        return
    
    print(f"\n📂 Found {len(sessions)} log session(s):\n")
    for i, session in enumerate(sessions):
        print(f"  {i+1}. {session.name}")
    
    # Analyze most recent session
    print(f"\n🔍 Analyzing most recent session...")
    latest = sessions[-1]
    stats = analyzer.analyze_session(latest)
    analyzer.print_session_report(stats)
    
    # Compare all sessions if multiple exist
    if len(sessions) > 1:
        analyzer.compare_ai_behaviors(sessions)
    
    # Export training data
    if len(sys.argv) > 1 and sys.argv[1] == "--export":
        output_file = sys.argv[2] if len(sys.argv) > 2 else "training_data.csv"
        analyzer.export_training_data(sessions, output_file)
    else:
        print("\n💡 Tip: Run with --export to create training dataset")
        print("   python analyze-ai-logs.py --export training_data.csv")

if __name__ == "__main__":
    main()

# In-Game Menu Testing Guide

## Overview
This document describes how to test the new in-game menu system that was added to allow players to access options during live gameplay.

## Prerequisites
- Server running (headless Godot server)
- Client connected to the game
- Active match in progress

## Test Cases

### 1. Menu Toggle (ESC Key)
**Steps:**
1. Join a match and wait for gameplay to start
2. Press ESC key
3. Verify menu appears as semi-transparent overlay on left side
4. Verify game continues running in background (players moving, bombs exploding, timer counting)
5. Press ESC key again
6. Verify menu closes

**Expected Result:** Menu toggles visibility on ESC press, game continues running

### 2. Resume Battle Button
**Steps:**
1. Open menu with ESC
2. Click "Resume Battle" button
3. Verify menu closes instantly

**Expected Result:** Menu closes when Resume Battle is clicked

### 3. Match Status Panel
**Steps:**
1. Open menu with ESC
2. Click "Match Status" button
3. Verify panel shows:
   - Time Remaining (formatted as M:SS)
   - Players Alive count (X / Total)
   - Rules (e.g., "Free For All")
4. Click "Back" button
5. Verify returns to main menu

**Expected Result:** Match status displays current game state, back button works

### 4. Player List Panel
**Steps:**
1. Open menu with ESC
2. Click "Player List" button
3. Verify panel shows all players in match
4. Verify dead players are marked as "(Dead)" with gray text
5. Verify each player has "Mute" and "Report" buttons
6. Click "Mute" on a player
7. Verify console log shows mute action
8. Click "Report" on a player
9. Verify console log shows report action
10. Click "Back" button
11. Verify returns to main menu

**Expected Result:** Player list shows all players with action buttons, back button works

### 5. Options Panel
**Steps:**
1. Open menu with ESC
2. Click "Options" button
3. Verify panel shows:
   - Master Volume slider (default 80%)
   - Music Volume slider (default 70%)
   - SFX Volume slider (default 90%)
   - Controls reference text
4. Move Master Volume slider
5. Verify value label updates (e.g., "85%")
6. Move Music Volume slider
7. Verify value label updates
8. Move SFX Volume slider
9. Verify value label updates
10. Click "Back" button
11. Verify returns to main menu

**Expected Result:** Options panel shows sliders that update labels, back button works

### 6. Leave Match Confirmation
**Steps:**
1. Open menu with ESC
2. Click "Leave Match" button
3. Verify confirmation panel appears with warning text
4. Click "Cancel" button
5. Verify returns to main menu
6. Click "Leave Match" again
7. Click "Yes, Leave Match" button
8. Verify client disconnects from server
9. Verify returns to login screen

**Expected Result:** Leave match requires confirmation, successfully disconnects

### 7. Menu Updates During Gameplay
**Steps:**
1. Open menu with ESC
2. Click "Match Status"
3. Wait 10 seconds (leave menu open)
4. Verify timer continues to count down
5. Return to main menu and click "Player List"
6. Wait for a player to die in the background
7. Verify player list updates to show dead player

**Expected Result:** Menu data updates in real-time based on game state

### 8. Menu Appearance
**Steps:**
1. Open menu with ESC
2. Verify:
   - Semi-transparent dark overlay covers entire screen
   - Menu panel is positioned on the left side
   - Text is readable
   - Buttons are properly sized and aligned
   - All panels fit within the menu container

**Expected Result:** Menu has proper visual styling and layout

## Known Limitations
- Mute functionality is placeholder (prints to console)
- Report functionality is placeholder (prints to console)
- Audio sliders don't currently affect actual audio (placeholders)

## Notes
- The menu is designed to be non-pausing since this is a multiplayer game with server authority
- Game state continues to update in the background while menu is open
- Menu uses CanvasLayer with layer 110 (above HUD which is 100)

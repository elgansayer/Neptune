# Character Select Screen Implementation

## Overview
The Character Select screen is designed for 1080p resolution (1920x1080) with a modern, sci-fi aesthetic featuring character customization, nickname input, and color selection.

## Scene Structure

### Root: CanvasLayer → RootControl (Full Screen Control)
- **BackgroundTexture**: Full-screen background with "Keep Aspect Covered" stretch mode
  - Asset: `res://art/backgrounds/character_select_bg.png` (placeholder: subtle sci-fi/grid pattern)

### MainPanelContainer (1600x900px, centered)
Custom StyleBox: `res://themes/panel_border_style.tres`
- Dark, semi-transparent background
- Rounded corners with subtle glow
- Border highlighting

## Left Panel: Character Roster (40% width)

### Components:
1. **RosterTitle**: "SELECT BOMBER"
   - Font: Custom DynamicFont (48pt, bold, outlined)
   - Centered alignment

2. **RosterScrollContainer**
   - Vertical-only scrolling
   - Contains **CharacterGrid**:
     - 4 columns grid layout
     - 15px horizontal/vertical separation
     - Dynamically populated with **TextureButton** nodes

3. **Character Portrait Buttons** (120x120px each)
   - **Normal**: `_idle.png` state
   - **Hover**: `_hover.png` (slightly brighter/animated)
   - **Pressed**: `_pressed.png` (depressed effect)
   - **Selected**: `_selected.png` (prominent highlight border)
   - Tooltip shows character name

## Right Panel: Character Details (60% width)

### Components:

1. **DetailTitle**: "YOUR BOMBER"
   - Font: 48pt, bold, outlined, centered

2. **PreviewAndNameHBox**
   - **CharacterPreviewContainer** (256x256px):
     - Darker panel with inner shadow
     - Contains **AnimatedSprite2D**: plays "Idle" animation
     - SpriteFrames loaded from character data
   
   - **NicknameVBox**:
     - Label: "IN-GAME NICKNAME" (20pt)
     - LineEdit: 50px height, 16 char max
       - Placeholder: "Enter your name"
       - Custom styling: dark background, glowing border on focus

3. **ColorOptionsVBox**
   - Label: "PRIMARY COLOR" (20pt)
   - ColorPickerButton (50px height)
     - Text: "Choose Color"
     - Tooltip: "Select your bomber's main color."

4. **LorePanelContainer** (expands to fill vertical space)
   - Lighter, semi-transparent panel
   - **CharacterNameLabel**: Character display name (36pt, centered)
   - **BioTitle**: "BOMBER BIO" (20pt)
   - **CharacterBioText**: RichTextLabel
     - BBCode enabled for rich formatting
     - Scrollable bio text
     - Color-coded text

5. **ButtonsHBox** (bottom of panel)
   - **BackButton** (200x60px):
     - Text: "BACK"
     - Returns to main menu
   - **ConfirmButton** (200x60px):
     - Text: "CONFIRM"
     - Proceeds with selection

## Audio Components
Three AudioStreamPlayer nodes for UI feedback:
- **AudioClickPlayer**: Button clicks (-5dB)
- **AudioHoverPlayer**: Hover sounds (-10dB)
- **AudioSelectPlayer**: Character selection (-3dB)

## Script Functionality (scripts/CharacterSelect.gd)

### Features:
1. **Dynamic Character Loading**
   - Scans `res://characters/` directory
   - Loads character data from JSON files
   - Fallback to default character if none found

2. **Character Data Structure**
   ```gdscript
   class CharacterData:
       var id: String
       var display_name: String
       var bio: String (BBCode formatted)
       var sprite_frames: SpriteFrames
       var portrait_idle/hover/pressed/selected: Texture2D
       var default_color: Color
   ```

3. **Player Preferences**
   - Saves to `user://player_preferences.cfg`
   - Remembers: nickname, color, last character
   - Auto-loads on scene start

4. **Color Customization**
   - Color picker modulates character preview sprite
   - Real-time preview of color changes
   - Saved with player preferences

5. **Signals**
   - `character_selected(character_id, nickname, primary_color)`
   - `back_pressed()`

## Asset Requirements

### Directories Created:
- `art/backgrounds/` - Background textures
- `themes/` - StyleBox and Theme resources
- `fonts/` - Custom font files
- `characters/portraits/` - Character portrait images

### Expected Assets:
1. **Backgrounds**:
   - `art/backgrounds/character_select_bg.png`

2. **Fonts**:
   - `fonts/bomberman_font.ttf`

3. **Character Portraits** (per character):
   - `characters/portraits/{character}_idle.png`
   - `characters/portraits/{character}_hover.png`
   - `characters/portraits/{character}_pressed.png`
   - `characters/portraits/{character}_selected.png`

4. **Character Data**:
   - `characters/{character}.json` - Character metadata
   - `characters/{character}.tres` - SpriteFrames resource

### Character JSON Format:
```json
{
    "id": "blue_bomber",
    "name": "Blue Bomber",
    "bio": "[color=#AAAAAA]A swift and tactical bomber...[/color]",
    "default_color": "#5555FF",
    "sprite_frames": "res://characters/blue_bomber.tres",
    "portrait_base": "res://characters/portraits/blue_bomber"
}
```

## Styling Theme

### Color Palette:
- **Panels**: Dark blues/greys (RGB: 25, 25, 40, 85% opacity)
- **Borders**: Bright cyan/blue (RGB: 77, 128, 204)
- **Highlights**: Orange/yellow/cyan for interactive elements
- **Text**: White with dark outlines for contrast

### Visual Effects:
- Rounded corners (10px radius)
- Subtle drop shadows (5px, semi-transparent)
- Glow effects on hover
- Smooth transitions for button states

## Integration with Game Flow

1. **Entry Point**: Called from Main Menu
2. **Confirmation Flow**:
   - Validates nickname (not empty)
   - Emits `character_selected` signal with data
   - Parent scene handles transition to game/lobby
3. **Back Button**:
   - Emits `back_pressed` signal
   - Returns to Main Menu without saving

## Accessibility Features

- Tooltips on all interactive elements
- Keyboard navigation support (Tab/Enter)
- Focus indicators on buttons
- Clear visual feedback for all interactions
- Scrollable character grid for many characters
- Text input validation

## Performance Considerations

- Characters loaded once on `_ready()`
- Portrait buttons created dynamically
- Sprite animations only play when visible
- Config file saves are lightweight
- No heavy computations in main thread

## Future Enhancements

- Character unlock system
- Animation previews (walk/bomb cycles)
- Voice line samples
- Character stats display
- Costume/skin variants
- Team color presets
- Character filtering/search
- Favorite characters system

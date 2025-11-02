That is the level of detail I enjoy! Drawing from technical analysis of the classic *Bomberman* engine—which *Saturn Bomberman* inherited and polished—here is the complete, technical breakdown of the character's movement system.

---

## 🔬 Sega Saturn Bomberman: Technical Movement Breakdown

The movement system is a highly refined example of a **Hybrid Grid-Based, Continuous Movement Model**. It uses floating-point position for fluidity, while relying on the underlying tile grid for all gameplay collisions and interactions.

### I. Character Position & Type

* **Coordinate System (Type):** The player's position is **continuous**, tracked via a floating-point coordinate pair $(x, y)$ (e.g., $1024 \times 1024$ pixels per tile).
* **Collision Box:** The character's hitbox is typically a small circle or square centered on $(x, y)$, deliberately sized to be **smaller than the tile width** to allow for sub-tile movement and crucial corner-sliding.

### II. Speed and Velocity

The character's speed is a base value (e.g., $V_{\text{base}}$) modified by the cumulative effect of **Roller Skates ($\text{Speed Up}$)** power-ups.

| Mechanic | Detail | Speed Effect |
| :--- | :--- | :--- |
| **Base Speed** | Initial movement speed (e.g., $V_{\text{initial}}$). | $\text{1 tile per } T_{\text{base}}$ time (e.g., $2.0-2.5$ tiles/sec). |
| **Roller Skates** | Each collected Skate applies a **cumulative multiplier** (e.g., $+12.5\%$). | Speed increases additively: $V_{\text{total}} = V_{\text{initial}} \times (1 + n \times \text{speed\_multiplier})$. |
| **Geta (Sandals)** | An inverse power-up that applies a negative multiplier. | Speed is severely *decreased*, making movement slow and imprecise. |
| **Tapping vs. Held Down** | **Tapping** a direction results in a brief acceleration followed by immediate deceleration upon release, covering a small distance. **Holding** a direction maintains constant $V_{\text{total}}$. | In Saturn Bomberman, there is generally **no difference in speed output** between tap and hold; the distinction lies in control and the activation of the **Gradual Move** system (see below). |

### III. Directional Input and Acceleration

#### A. Pressing a Direction (Held Down)
1.  **Velocity Vector:** Pressing a direction on the D-pad immediately generates a **velocity vector** ($\vec{v}$) in the cardinal direction pressed.
2.  **Continuous Movement:** The character's position is updated every frame: $\text{Position}_{\text{new}} = \text{Position}_{\text{current}} + \vec{v} \times \Delta t$.
3.  **Off-Grid Movement:** The character can be positioned anywhere within a tile. Movement is **fully continuous** as long as the button is held, allowing the player to hug walls or place a bomb perfectly off-centre to create a tight squeeze for an opponent.

#### B. Releasing a Direction (Tap)
1.  **Immediate Deceleration:** When the D-pad input stops, the player's velocity immediately drops to zero.
2.  **Gradual Grid Alignment (Snap-to-Centre):** This is where a **tap** differs from a **hold**. Once the character stops, the game triggers an automatic alignment function:
    * **Logic:** If the character's position is more than a tiny threshold away from the center of their current grid tile, a small, corrective force is applied towards the center.
    * **Effect:** The character $\text{slides slowly}$ towards the true center of the grid space. This is done to ensure the character is perfectly aligned when dropping the next bomb or initiating a special power-up action (like throwing a bomb). A player who taps will trigger this alignment constantly.

### IV. Collision and Cornering Mechanics

#### A. What Happens When Blocked (Against a Wall)
* **Collision:** If the character's movement vector points directly into a solid object (Hard Block, Soft Block, Bomb), the movement along that axis is **immediately halted**.
* **Result:** The character maintains its off-grid position but the velocity vector $\vec{v}$ becomes zero in the blocked axis (e.g., if moving right, $V_{x} = 0$). The walking animation continues to play (the "walking against a block" animation) as long as the input is held.

#### B. Automatic Cornering ("Wall Hugging")
This is a sophisticated collision detection feature that gives the movement its smooth feel:

1.  **Attempted Movement:** The player is moving (e.g., primarily $\text{Up}$) but is also holding a slight $\text{Left}$ angle (off-grid alignment).
2.  **Collision Prediction:** The character hits the corner of a block directly ahead (blocking the $\text{Up}$ movement).
3.  **Vector Decomposition & Sliding:** Instead of stopping all movement, the system checks the unblocked axis. Since the player had a slight $\text{Left}$ movement component, the system cancels the vertical ($\text{Up}$) velocity but allows the **horizontal velocity ($\text{Left}$) to continue**.
4.  **Result:** The character seamlessly "slides" or "hugs" the corner, turning the corner without losing significant momentum or having to stop and re-align input. This highly technical feature makes movement feel exceptionally responsive and is critical for speed and evasion at high levels of play.

### V. Power-Up Movement Transformation

Movement can be entirely overridden by power-ups:

* **Tirra Mounts:** Riding a Tirra (dinosaur) grants an extra hit and completely new movement abilities (e.g., the Green Tirra's fast **Dash** movement or the Pink Tirra's ability to **Jump** over single blocks/bombs).
* **Bomb Pass / Wall Pass:** These items temporarily remove collision detection for bombs or soft blocks, allowing the player to glide through the maze elements and ignore the grid-based restriction of movement entirely.
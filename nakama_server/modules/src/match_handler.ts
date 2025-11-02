/// <reference types="@heroiclabs/nakama-common" />

// --- Enums ---
enum PowerUpType {
    ExtraBomb,
    BombRadius,
    BombKick,
    SpeedUp,
    SpeedDown,
}

// --- Interfaces ---
interface Player {
    id: string;
    username: string;
    position: { x: number, y: number };  // Grid position (tile coordinates)
    pixel_position: { x: number, y: number };  // Pixel position for smooth movement
    isAlive: boolean;
    lastProcessedSequence: number;
    bombCount: number;
    bombRadius: number;
    character: string;
    hasBombKick: boolean;
    speed: number;  // Movement speed multiplier
}

interface Bomb {
    owner_id: string;
    position: { x: number, y: number };
    timer: number;
    isKicked: boolean;  // Is the bomb currently sliding
    kickDirection?: { x: number, y: number };  // Direction bomb is sliding
}

interface Explosion {
    position: { x: number, y: number };
    timer: number;
    tiles: { x: number, y: number }[];  // All tiles affected by this explosion
}

interface PowerUp {
    type: PowerUpType;
    position: { x: number, y: number };
}

export interface GameState {
    players: { [id: string]: Player };
    bombs: Bomb[];
    explosions: Explosion[];
    powerUps: PowerUp[];
    grid: number[][];
    tick: number;
}

// --- Constants ---
export const TICK_RATE = 20;
const BOMB_TIMER = 3 * TICK_RATE;
const EXPLOSION_TIMER = 1 * TICK_RATE;
const GRID_WIDTH = 15;
const GRID_HEIGHT = 13;
const TILE_SIZE = 64;  // Match client's TILE_SIZE
const INITIAL_BOMB_RADIUS = 2;
const INITIAL_BOMB_COUNT = 1;
const POWERUP_SPAWN_CHANCE = 0.5; // 50% chance
const MAX_POSITION_ERROR = 150;  // Max pixels client can deviate before correction

// --- Match Handler ---

export const matchInit: nkruntime.MatchInitFunction<GameState> = (ctx, logger, nk, params) => {
    logger.info("New Bomberman match initialized.");

    let grid: number[][] = [];
    try {
        const fileContent = nk.fileRead("res/maps/default.json");
        const mapData = JSON.parse(fileContent);
        grid = mapData.grid;
    } catch (error: unknown) {
        let errorMessage = "Unknown error";
        if (error instanceof Error) {
            errorMessage = error.message;
        }
        logger.error("Error reading map file: %s", errorMessage);
        // Fallback to a default empty grid if map loading fails
        grid = Array(GRID_HEIGHT).fill(Array(GRID_WIDTH).fill(0));
    }

    return {
        state: {
            players: {},
            bombs: [],
            explosions: [],
            powerUps: [],
            grid: grid,
            tick: 0,
        },
        tickRate: TICK_RATE,
        label: "BombermanMatch"
    };
};

export const matchJoin: nkruntime.MatchJoinFunction<GameState> = (ctx, logger, nk, dispatcher, tick, state, presences) => {
    // Spawn positions for up to 10 players (corners and edges)
    const spawnPositions = [
        { x: 1, y: 1 },              // Top-left
        { x: GRID_WIDTH - 2, y: 1 }, // Top-right
        { x: 1, y: GRID_HEIGHT - 2 },              // Bottom-left
        { x: GRID_WIDTH - 2, y: GRID_HEIGHT - 2 }, // Bottom-right
        { x: Math.floor(GRID_WIDTH / 2), y: 1 },   // Top-center
        { x: Math.floor(GRID_WIDTH / 2), y: GRID_HEIGHT - 2 }, // Bottom-center
        { x: 1, y: Math.floor(GRID_HEIGHT / 2) },  // Left-center
        { x: GRID_WIDTH - 2, y: Math.floor(GRID_HEIGHT / 2) }, // Right-center
        { x: 3, y: 3 },              // Inner top-left
        { x: GRID_WIDTH - 4, y: GRID_HEIGHT - 4 }  // Inner bottom-right
    ];
    
    const characters = ["Player", "Player2", "Player3", "Player4", "Player5", 
                        "Player6", "Player7", "Player8", "Player9", "Player10"];
    
    for (const p of presences) {
        logger.info(`Player ${p.username} joined.`);
        const playerCount = Object.keys(state.players).length;
        
        // Assign spawn position and character based on player count
        const startPos = spawnPositions[playerCount % spawnPositions.length];
        const character = characters[playerCount % characters.length];
        
        state.players[p.userId] = {
            id: p.userId,
            username: p.username,
            position: startPos,
            pixel_position: { x: startPos.x * TILE_SIZE + TILE_SIZE / 2, y: startPos.y * TILE_SIZE + TILE_SIZE / 2 },
            isAlive: true,
            lastProcessedSequence: 0,
            bombCount: INITIAL_BOMB_COUNT,
            bombRadius: INITIAL_BOMB_RADIUS,
            character: character,
            hasBombKick: false,
            speed: 1.0,
        };
    }
    return { state };
};

export const matchLeave: nkruntime.MatchLeaveFunction<GameState> = (ctx, logger, nk, dispatcher, tick, state, presences) => {
    for (const p of presences) {
        logger.info(`Player ${p.username} left.`);
        delete state.players[p.userId];
    }
    return { state };
};

export const matchLoop: nkruntime.MatchLoopFunction<GameState> = (ctx, logger, nk, dispatcher, tick, state, messages) => {
    state.tick = tick;

    // --- Process Inputs ---
    for (const m of messages) {
        if (m.opCode === 1) {
            const input = JSON.parse(nk.binaryToString(m.data));
            const player = state.players[m.sender.userId];
            if (!player || !player.isAlive) continue;

            // Update the last processed input sequence for this player.
            if (input.seq) {
                player.lastProcessedSequence = input.seq;
            }

            // Pixel-based Movement with Collision Detection
            if (input.position_x !== undefined && input.position_y !== undefined) {
                const clientPixelPos = { x: input.position_x, y: input.position_y };
                
                // Validate the position isn't too far from current (anti-cheat)
                const currentPixelPos = player.pixel_position;
                const dx = clientPixelPos.x - currentPixelPos.x;
                const dy = clientPixelPos.y - currentPixelPos.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance <= MAX_POSITION_ERROR) {
                    // Check if the pixel position is valid (not inside walls)
                    if (isPixelPositionWalkable(state.grid, clientPixelPos.x, clientPixelPos.y)) {
                        player.pixel_position = clientPixelPos;
                        // Update grid position for bomb placement and power-up collection
                        player.position = {
                            x: Math.floor(clientPixelPos.x / TILE_SIZE),
                            y: Math.floor(clientPixelPos.y / TILE_SIZE)
                        };
                    }
                }
            }

            // Bomb Placement
            if (input.place_bomb) {
                const existingBombs = state.bombs.filter(b => b.owner_id === player.id);
                if (existingBombs.length < player.bombCount) {
                    const existingBombAtPos = state.bombs.find(b => b.position.x === Math.round(player.position.x) && b.position.y === Math.round(player.position.y));
                    if (!existingBombAtPos) {
                        state.bombs.push({ 
                            owner_id: player.id, 
                            position: { x: Math.round(player.position.x), y: Math.round(player.position.y) }, 
                            timer: BOMB_TIMER,
                            isKicked: false
                        });
                    }
                }
            }
        }
    }

    // --- Update Game Logic ---

    // Bomb Kick - Check if player with BombKick walks into a bomb
    for (const player of Object.values(state.players)) {
        if (player.isAlive && player.hasBombKick) {
            for (const bomb of state.bombs) {
                // Check if player is on same tile as bomb and bomb is not already kicked
                if (!bomb.isKicked && bomb.position.x === player.position.x && bomb.position.y === player.position.y) {
                    // Determine kick direction from player's recent movement
                    // This is a simplified version - ideally track player's velocity
                    // For now, we'll handle this when client sends kick action
                }
            }
        }
    }

    // Update Kicked Bombs Movement
    for (const bomb of state.bombs) {
        if (bomb.isKicked && bomb.kickDirection) {
            const nextX = bomb.position.x + bomb.kickDirection.x;
            const nextY = bomb.position.y + bomb.kickDirection.y;
            
            // Check if next position is walkable
            if (isWalkable(state.grid, nextX, nextY)) {
                // Check for collision with other bombs
                const bombAtNext = state.bombs.find(b => b !== bomb && b.position.x === nextX && b.position.y === nextY);
                if (!bombAtNext) {
                    bomb.position = { x: nextX, y: nextY };
                } else {
                    // Hit another bomb, stop
                    bomb.isKicked = false;
                    delete bomb.kickDirection;
                }
            } else {
                // Hit a wall, stop
                bomb.isKicked = false;
                delete bomb.kickDirection;
            }
        }
    }

    // Power-up Collection
    for (const player of Object.values(state.players)) {
        if (player.isAlive) {
            const collectedPowerUpIndex = state.powerUps.findIndex(p => Math.round(player.position.x) === p.position.x && Math.round(player.position.y) === p.position.y);
            if (collectedPowerUpIndex !== -1) {
                const powerUp = state.powerUps[collectedPowerUpIndex];
                switch (powerUp.type) {
                    case PowerUpType.ExtraBomb:
                        player.bombCount++;
                        break;
                    case PowerUpType.BombRadius:
                        player.bombRadius++;
                        break;
                    case PowerUpType.BombKick:
                        player.hasBombKick = true;
                        break;
                    case PowerUpType.SpeedUp:
                        player.speed = Math.min(player.speed + 0.2, 2.0);  // Cap at 2x speed
                        break;
                    case PowerUpType.SpeedDown:
                        player.speed = Math.max(player.speed - 0.2, 0.5);  // Minimum 0.5x speed
                        break;
                }
                state.powerUps.splice(collectedPowerUpIndex, 1);
            }
        }
    }

    // Bomb Timers & Explosions
    const explodingBombs: Bomb[] = [];
    state.bombs = state.bombs.filter(bomb => {
        bomb.timer--;
        if (bomb.timer <= 0) {
            explodingBombs.push(bomb);
            return false;
        }
        return true;
    });

    for (const bomb of explodingBombs) {
        const explosionTiles = calculateExplosionTiles(state, bomb);
        state.explosions.push({ 
            position: bomb.position, 
            timer: EXPLOSION_TIMER,
            tiles: explosionTiles
        });
        handleExplosion(state, bomb, explosionTiles, logger);
    }

    // Explosion Timers
    state.explosions = state.explosions.filter(exp => exp.timer-- > 0);

    // --- Broadcast State ---
    dispatcher.broadcastMessage(2, JSON.stringify(state));

    return { state };
};

// --- Helper Functions ---

const isWalkable = (grid: number[][], x: number, y: number): boolean => {
    const gridX = Math.round(x);
    const gridY = Math.round(y);
    return grid[gridY] && grid[gridY][gridX] === 0;
};

// Check if a pixel position is walkable (simple center-point check)
const isPixelPositionWalkable = (grid: number[][], pixelX: number, pixelY: number): boolean => {
    const gridX = Math.floor(pixelX / TILE_SIZE);
    const gridY = Math.floor(pixelY / TILE_SIZE);
    
    // Out of bounds check
    if (gridY < 0 || gridY >= grid.length || gridX < 0 || gridX >= grid[0].length) {
        return false;
    }
    
    // Wall check (0 = walkable)
    return grid[gridY][gridX] === 0;
};

// Calculate which tiles are affected by an explosion
const calculateExplosionTiles = (state: GameState, bomb: Bomb): { x: number, y: number }[] => {
    const owner = Object.values(state.players).find(p => p.id === bomb.owner_id);
    const bombRadius = owner ? owner.bombRadius : INITIAL_BOMB_RADIUS;

    const directions = [{x: 0, y: 1}, {x: 0, y: -1}, {x: 1, y: 0}, {x: -1, y: 0}];
    const explosionTiles = [{x: bomb.position.x, y: bomb.position.y}];

    for (const dir of directions) {
        for (let i = 1; i <= bombRadius; i++) {
            const x = bomb.position.x + dir.x * i;
            const y = bomb.position.y + dir.y * i;

            if (x < 0 || y < 0 || x >= GRID_WIDTH || y >= GRID_HEIGHT) break;

            const tile = state.grid[y][x];
            explosionTiles.push({x, y});

            if (tile === 1 || tile === 2) { // Stop at any wall
                break;
            }
        }
    }

    return explosionTiles;
};

const handleExplosion = (state: GameState, bomb: Bomb, explosionTiles: { x: number, y: number }[], logger: nkruntime.Logger) => {
    // Destroy breakable walls and spawn power-ups
    for (const tile of explosionTiles) {
        if (state.grid[tile.y][tile.x] === 1) { // Breakable wall
            state.grid[tile.y][tile.x] = 0;
            if (Math.random() < POWERUP_SPAWN_CHANCE) {
                // Random power-up type
                const rand = Math.random();
                let powerUpType: PowerUpType;
                if (rand < 0.3) {
                    powerUpType = PowerUpType.ExtraBomb;
                } else if (rand < 0.5) {
                    powerUpType = PowerUpType.BombRadius;
                } else if (rand < 0.7) {
                    powerUpType = PowerUpType.BombKick;
                } else if (rand < 0.85) {
                    powerUpType = PowerUpType.SpeedUp;
                } else {
                    powerUpType = PowerUpType.SpeedDown;
                }
                state.powerUps.push({ type: powerUpType, position: { x: tile.x, y: tile.y } });
            }
        }
    }

    // Check for players in explosion tiles
    for (const player of Object.values(state.players)) {
        if (player.isAlive) {
            // Use pixel position for more accurate collision detection
            const playerTileX = Math.floor(player.pixel_position.x / TILE_SIZE);
            const playerTileY = Math.floor(player.pixel_position.y / TILE_SIZE);
            
            for (const tile of explosionTiles) {
                if (playerTileX === tile.x && playerTileY === tile.y) {
                    player.isAlive = false;
                    logger.info(`Player ${player.username} was eliminated.`);
                    break;
                }
            }
        }
    }
};
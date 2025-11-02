/// <reference types="@heroiclabs/nakama-common" />

// Minimal working version with pixel-based movement
// All code inlined to avoid module system issues

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
    position: { x: number, y: number };
    pixel_position: { x: number, y: number };
    isAlive: boolean;
    lastProcessedSequence: number;
    bombCount: number;
    bombRadius: number;
    character: string;
    hasBombKick: boolean;
    speed: number;
}

interface Bomb {
    owner_id: string;
    position: { x: number, y: number };
    timer: number;
    isKicked: boolean;
    kickDirection?: { x: number, y: number };
}

interface Explosion {
    position: { x: number, y: number };
    timer: number;
    tiles: { x: number, y: number }[];
}

interface PowerUp {
    type: PowerUpType;
    position: { x: number, y: number };
}

interface GameState {
    players: { [id: string]: Player };
    bombs: Bomb[];
    explosions: Explosion[];
    powerUps: PowerUp[];
    grid: number[][];
    tick: number;
}

// --- Constants ---
const TICK_RATE = 20;
const BOMB_TIMER = 3 * TICK_RATE;
const EXPLOSION_TIMER = 1 * TICK_RATE;
const GRID_WIDTH = 15;
const GRID_HEIGHT = 13;
const TILE_SIZE = 64;
const INITIAL_BOMB_RADIUS = 2;
const INITIAL_BOMB_COUNT = 1;
const POWERUP_SPAWN_CHANCE = 0.5;
const MAX_POSITION_ERROR = 150;

// --- Helper Functions ---
const isWalkable = (grid: number[][], x: number, y: number): boolean => {
    const gridX = Math.round(x);
    const gridY = Math.round(y);
    return grid[gridY] && grid[gridY][gridX] === 0;
};

const isPixelPositionWalkable = (state: GameState, pixelX: number, pixelY: number, playerId: string): boolean => {
    const PLAYER_HALF_WIDTH = 28.0;
    const grid = state.grid;
    
    // Check 9 points: center + 4 edges + 4 corners
    const checkPoints = [
        { x: pixelX, y: pixelY },
        { x: pixelX + PLAYER_HALF_WIDTH, y: pixelY },
        { x: pixelX - PLAYER_HALF_WIDTH, y: pixelY },
        { x: pixelX, y: pixelY + PLAYER_HALF_WIDTH },
        { x: pixelX, y: pixelY - PLAYER_HALF_WIDTH },
        { x: pixelX + PLAYER_HALF_WIDTH, y: pixelY + PLAYER_HALF_WIDTH },
        { x: pixelX - PLAYER_HALF_WIDTH, y: pixelY + PLAYER_HALF_WIDTH },
        { x: pixelX + PLAYER_HALF_WIDTH, y: pixelY - PLAYER_HALF_WIDTH },
        { x: pixelX - PLAYER_HALF_WIDTH, y: pixelY - PLAYER_HALF_WIDTH }
    ];
    
    const player = state.players[playerId];
    const currentGridX = Math.floor(player.pixel_position.x / TILE_SIZE);
    const currentGridY = Math.floor(player.pixel_position.y / TILE_SIZE);
    
    for (const point of checkPoints) {
        const gridX = Math.floor(point.x / TILE_SIZE);
        const gridY = Math.floor(point.y / TILE_SIZE);
        
        // Out of bounds check
        if (gridY < 0 || gridY >= grid.length || gridX < 0 || gridX >= grid[0].length) {
            return false;
        }
        
        // Wall/block check
        if (grid[gridY][gridX] !== 0) {
            return false;
        }
        
        // Bomb collision check
        for (const bomb of state.bombs) {
            // Allow movement if we're currently standing on this bomb
            if (currentGridX === bomb.position.x && currentGridY === bomb.position.y) {
                continue;
            }
            
            const bombCenterX = bomb.position.x * TILE_SIZE + TILE_SIZE / 2;
            const bombCenterY = bomb.position.y * TILE_SIZE + TILE_SIZE / 2;
            const dx = Math.abs(point.x - bombCenterX);
            const dy = Math.abs(point.y - bombCenterY);
            
            if (dx < (PLAYER_HALF_WIDTH + 18.0) && dy < (PLAYER_HALF_WIDTH + 18.0)) {
                return false;
            }
        }
    }
    
    return true;
};

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
            explosionTiles.push({x: x, y: y});

            if (tile === 1 || tile === 2) {
                break;
            }
        }
    }

    return explosionTiles;
};

const handleExplosion = (state: GameState, bomb: Bomb, explosionTiles: { x: number, y: number }[], logger: nkruntime.Logger) => {
    for (const tile of explosionTiles) {
        if (state.grid[tile.y][tile.x] === 1) {
            state.grid[tile.y][tile.x] = 0;
            if (Math.random() < POWERUP_SPAWN_CHANCE) {
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

    for (const player of Object.values(state.players)) {
        if (player.isAlive) {
            for (const tile of explosionTiles) {
                if (Math.round(player.position.x) === tile.x && Math.round(player.position.y) === tile.y) {
                    player.isAlive = false;
                    logger.info(`Player ${player.username} was eliminated.`);
                    break;
                }
            }
        }
    }
};

// --- Match Handler Functions ---
const matchInit: nkruntime.MatchInitFunction<GameState> = (ctx, logger, nk, params) => {
    logger.info("New Bomberman match initialized.");

    let grid: number[][] = [];
    try {
        const fileContent = nk.fileRead("../res/maps/default.json");
        const mapData = JSON.parse(fileContent);
        grid = mapData.grid;
        logger.info("Map loaded successfully with %d rows", grid.length);
    } catch (error: unknown) {
        let errorMessage = "Unknown error";
        if (error instanceof Error) {
            errorMessage = error.message;
        }
        logger.error("Error reading map file: %s", errorMessage);
        logger.info("Creating empty fallback grid");
        grid = Array(GRID_HEIGHT).fill(null).map(() => Array(GRID_WIDTH).fill(0));
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

const matchJoin: nkruntime.MatchJoinFunction<GameState> = (ctx, logger, nk, dispatcher, tick, state, presences) => {
    const spawnPositions = [
        { x: 1, y: 1 },
        { x: GRID_WIDTH - 2, y: 1 },
        { x: 1, y: GRID_HEIGHT - 2 },
        { x: GRID_WIDTH - 2, y: GRID_HEIGHT - 2 },
        { x: Math.floor(GRID_WIDTH / 2), y: 1 },
        { x: Math.floor(GRID_WIDTH / 2), y: GRID_HEIGHT - 2 },
        { x: 1, y: Math.floor(GRID_HEIGHT / 2) },
        { x: GRID_WIDTH - 2, y: Math.floor(GRID_HEIGHT / 2) },
        { x: 3, y: 3 },
        { x: GRID_WIDTH - 4, y: GRID_HEIGHT - 4 }
    ];
    
    const characters = ["Player", "Player2", "Player3", "Player4", "Player5",
                        "Player6", "Player7", "Player8", "Player9", "Player10"];
    
    for (const p of presences) {
        logger.info(`Player ${p.username} joined.`);
        const playerCount = Object.keys(state.players).length;
        
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
    return { state: state };
};

const matchLeave: nkruntime.MatchLeaveFunction<GameState> = (ctx, logger, nk, dispatcher, tick, state, presences) => {
    for (const p of presences) {
        logger.info(`Player ${p.username} left.`);
        delete state.players[p.userId];
    }
    return { state: state };
};

const matchLoop: nkruntime.MatchLoopFunction<GameState> = (ctx, logger, nk, dispatcher, tick, state, messages) => {
    state.tick = tick;

    for (const m of messages) {
        if (m.opCode === 1) {
            const input = JSON.parse(nk.binaryToString(m.data));
            const player = state.players[m.sender.userId];
            if (!player || !player.isAlive) continue;

            if (input.seq) {
                player.lastProcessedSequence = input.seq;
            }

            // Pixel-based Movement
            if (input.position_x !== undefined && input.position_y !== undefined) {
                const clientPixelPos = { x: input.position_x, y: input.position_y };
                
                const currentPixelPos = player.pixel_position;
                const dx = clientPixelPos.x - currentPixelPos.x;
                const dy = clientPixelPos.y - currentPixelPos.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance <= MAX_POSITION_ERROR) {
                    if (isPixelPositionWalkable(state, clientPixelPos.x, clientPixelPos.y, player.id)) {
                        player.pixel_position = clientPixelPos;
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
                    // Use floor to match how grid positions are calculated everywhere
                    const bombGridX = Math.floor(player.pixel_position.x / TILE_SIZE);
                    const bombGridY = Math.floor(player.pixel_position.y / TILE_SIZE);
                    const existingBombAtPos = state.bombs.find(b => b.position.x === bombGridX && b.position.y === bombGridY);
                    if (!existingBombAtPos) {
                        state.bombs.push({ 
                            owner_id: player.id, 
                            position: { x: bombGridX, y: bombGridY }, 
                            timer: BOMB_TIMER,
                            isKicked: false
                        });
                    }
                }
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
                        player.speed = Math.min(player.speed + 0.2, 2.0);
                        break;
                    case PowerUpType.SpeedDown:
                        player.speed = Math.max(player.speed - 0.2, 0.5);
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

    dispatcher.broadcastMessage(2, JSON.stringify(state));

    return { state: state };
};

const matchJoinAttempt: nkruntime.MatchJoinAttemptFunction<GameState> = (ctx, logger, nk, dispatcher, tick, state, presence, metadata) => {
    return { state: state, accept: true };
};

const matchTerminate: nkruntime.MatchTerminateFunction<GameState> = (ctx, logger, nk, dispatcher, tick, state, graceSeconds) => {
    return { state: state };
};

const matchSignal: nkruntime.MatchSignalFunction<GameState> = (ctx, logger, nk, dispatcher, tick, state, data) => {
    return { state: state };
};

// --- RPC Functions ---
const createBombermanMatch: nkruntime.RpcFunction = (ctx, logger, nk, payload) => {
    logger.info("RPC: create_bomberman_match called");
    
    // Create an authoritative match using the "bomberman" handler
    const matchId = nk.matchCreate("bomberman");
    
    logger.info("Created match with ID: " + matchId);
    
    // Return the match ID as JSON
    return JSON.stringify({ matchId: matchId });
};

// --- Main Init Function ---
function InitModule(ctx: nkruntime.Context, logger: nkruntime.Logger, nk: nkruntime.Nakama, initializer: nkruntime.Initializer) {
    logger.info("Bomberman server module loaded.");

    initializer.registerMatch("bomberman", {
        matchInit: matchInit,
        matchJoin: matchJoin,
        matchLeave: matchLeave,
        matchLoop: matchLoop,
        matchJoinAttempt: matchJoinAttempt,
        matchTerminate: matchTerminate,
        matchSignal: matchSignal
    });
    
    initializer.registerRpc("create_bomberman_match", createBombermanMatch);
    logger.info("Registered RPC: create_bomberman_match");
}

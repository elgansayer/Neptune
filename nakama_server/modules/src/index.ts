/// <reference types="@heroiclabs/nakama-common" />

// Import types from match_handler - we'll inline the code instead
// to avoid module system issues with Nakama

// Copy all the code from match_handler.ts here and make it work without exports

// --- Enums ---
enum PowerUpType {
    ExtraBomb,
    BombRadius,
}

// --- Interfaces ---
interface Player {
    id: string;
    username: string;
    position: { x: number, y: number };
    isAlive: boolean;
    lastProcessedSequence: number;
    bombCount: number;
    bombRadius: number;
    character: string;
}

interface Bomb {
    owner_id: string;
    position: { x: number, y: number };
    timer: number;
}

interface Explosion {
    position: { x: number, y: number };
    timer: number;
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
const INITIAL_BOMB_RADIUS = 2;
const INITIAL_BOMB_COUNT = 1;
const POWERUP_SPAWN_CHANCE = 0.5;

// --- Helper Functions ---
const isWalkable = (grid: number[][], x: number, y: number): boolean => {
    const gridX = Math.round(x);
    const gridY = Math.round(y);
    return grid[gridY] && grid[gridY][gridX] === 0;
};

const handleExplosion = (state: GameState, bomb: Bomb, logger: nkruntime.Logger) => {
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

            if (tile === 1) {
                state.grid[y][x] = 0;
                if (Math.random() < POWERUP_SPAWN_CHANCE) {
                    const powerUpType = Math.random() < 0.5 ? PowerUpType.ExtraBomb : PowerUpType.BombRadius;
                    state.powerUps.push({ type: powerUpType, position: { x, y } });
                }
                break;
            }
            if (tile === 2) {
                break;
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
        const fileContent = nk.fileRead("res/maps/default.json");
        const mapData = JSON.parse(fileContent);
        grid = mapData.grid;
    } catch (error: unknown) {
        let errorMessage = "Unknown error";
        if (error instanceof Error) {
            errorMessage = error.message;
        }
        logger.error("Error reading map file: %s", errorMessage);
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
    for (const p of presences) {
        logger.info(`Player ${p.username} joined.`);
        const playerCount = Object.keys(state.players).length;
        let startPos = { x: 1, y: 1 };
        let character = "Player";
        if (playerCount > 0) {
            startPos = { x: GRID_WIDTH - 2, y: GRID_HEIGHT - 2 };
            character = "Player2";
        }
        
        state.players[p.userId] = {
            id: p.userId,
            username: p.username,
            position: startPos,
            isAlive: true,
            lastProcessedSequence: 0,
            bombCount: INITIAL_BOMB_COUNT,
            bombRadius: INITIAL_BOMB_RADIUS,
            character: character,
        };
    }
    return { state };
};

const matchLeave: nkruntime.MatchLeaveFunction<GameState> = (ctx, logger, nk, dispatcher, tick, state, presences) => {
    for (const p of presences) {
        logger.info(`Player ${p.username} left.`);
        delete state.players[p.userId];
    }
    return { state };
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

            if (input.dx || input.dy) {
                const nextPos = { x: player.position.x + (input.dx || 0), y: player.position.y + (input.dy || 0) };
                if (isWalkable(state.grid, nextPos.x, nextPos.y)) {
                    player.position = nextPos;
                }
            }

            if (input.place_bomb) {
                const existingBombs = state.bombs.filter(b => b.owner_id === player.id);
                if (existingBombs.length < player.bombCount) {
                    const existingBombAtPos = state.bombs.find(b => b.position.x === Math.round(player.position.x) && b.position.y === Math.round(player.position.y));
                    if (!existingBombAtPos) {
                        state.bombs.push({ owner_id: player.id, position: { x: Math.round(player.position.x), y: Math.round(player.position.y) }, timer: BOMB_TIMER });
                    }
                }
            }
        }
    }

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
                }
                state.powerUps.splice(collectedPowerUpIndex, 1);
            }
        }
    }

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
        state.explosions.push({ position: bomb.position, timer: EXPLOSION_TIMER });
        handleExplosion(state, bomb, logger);
    }

    state.explosions = state.explosions.filter(exp => exp.timer-- > 0);

    dispatcher.broadcastMessage(2, JSON.stringify(state));

    return { state };
};

// --- Main Init Function ---
function InitModule(ctx: nkruntime.Context, logger: nkruntime.Logger, nk: nkruntime.Nakama, initializer: nkruntime.Initializer) {
    logger.info("Bomberman server module loaded.");

    initializer.registerMatch<GameState>("bomberman", {
        matchInit,
        matchJoin,
        matchLeave,
        matchLoop,
        matchJoinAttempt: (ctx, logger, nk, dispatcher, tick, state, presence, metadata) => {
            return { state, accept: true };
        },
        matchTerminate: (ctx, logger, nk, dispatcher, tick, state, graceSeconds) => {
            return { state };
        },
        matchSignal: (ctx, logger, nk, dispatcher, tick, state, data) => {
            return { state };
        }
    });
}

// Make InitModule available to Nakama
!InitModule && InitModule;

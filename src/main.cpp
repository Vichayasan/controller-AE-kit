#include <Arduino.h>
#include <LiquidCrystal.h>

// ============================================================
// PIN MAPPING (Mega2560)
// LCD : RS=12, E=11, D4=5, D5=6, D6=7, D7=8
// Jump: P1=Pin2 (INT0), P2=Pin3 (INT1)
// Fire: P1=Pin18 (INT5), P2=Pin19 (INT4)
// ============================================================
LiquidCrystal lcd(12, 11, 5, 6, 7, 8);

#define BTN_JUMP_P1  2
#define BTN_JUMP_P2  3
#define BTN_FIRE_P1  18
#define BTN_FIRE_P2  19

// ============================================================
// DEBOUNCE
// ============================================================
#define DEBOUNCE_MS 50  // ignore presses within 50ms of last press

unsigned long lastJump01 = 0;
unsigned long lastJump02 = 0;
unsigned long lastFire01 = 0;
unsigned long lastFire02 = 0;

// ============================================================
// TERRAIN & SPRITES
// ============================================================
#define TERRAIN_WIDTH      16
#define SPRITE_TERRAIN_EMPTY ' '
#define BULLET_CHAR        '-'
#define SPRITE_JUMP_UPPER  '.'

#define HERO1_POSITION     1
#define HERO2_POSITION     14

#define HERO1_RUN1  1
#define HERO1_RUN2  2
#define HERO1_RUN3  3
#define HERO2_RUN1  4
#define HERO2_RUN2  5
#define HERO2_RUN3  6

// ============================================================
// HERO STATE MACHINE
// ============================================================
#define HERO_POSITION_RUN_LOWER_1  1
#define HERO_POSITION_RUN_LOWER_2  2
#define HERO_POSITION_RUN_LOWER_3  3
#define HERO_POSITION_JUMP_1       4
#define HERO_POSITION_JUMP_2       5
#define HERO_POSITION_JUMP_3       6
#define HERO_POSITION_JUMP_4       7
#define HERO_POSITION_JUMP_5       8
#define HERO_POSITION_JUMP_6       9
#define HERO_POSITION_JUMP_7       10
#define HERO_POSITION_JUMP_8       11
#define HERO_POSITION_RUN_UPPER_1  12
#define HERO_POSITION_RUN_UPPER_2  13
#define HERO_POSITION_RUN_UPPER_3  14

// ============================================================
// GLOBALS
// ============================================================
static char terrainUpper[TERRAIN_WIDTH + 1];
static char terrainLower[TERRAIN_WIDTH + 1];

volatile bool jumpPushed01 = false;
volatile bool jumpPushed02 = false;
volatile bool firePushed01 = false;
volatile bool firePushed02 = false;

bool shown01 = false;
bool shown02 = false;

struct Bullet {
  int8_t x;
  int8_t row;
  int8_t dir;
  bool   active;
};

Bullet bullet01 = {-1, 1, +1, false};
Bullet bullet02 = {-1, 1, -1, false};

// ============================================================
// INTERRUPTS (with debounce)
// ============================================================
void onJump01() {
  unsigned long now = millis();
  if (now - lastJump01 >= DEBOUNCE_MS) {
    jumpPushed01 = true;
    lastJump01 = now;
  }
}

void onJump02() {
  unsigned long now = millis();
  if (now - lastJump02 >= DEBOUNCE_MS) {
    jumpPushed02 = true;
    lastJump02 = now;
  }
}

void onFire01() {
  unsigned long now = millis();
  if (now - lastFire01 >= DEBOUNCE_MS) {
    firePushed01 = true;
    lastFire01 = now;
  }
}

void onFire02() {
  unsigned long now = millis();
  if (now - lastFire02 >= DEBOUNCE_MS) {
    firePushed02 = true;
    lastFire02 = now;
  }
}

// ============================================================
// GRAPHICS
// ============================================================
void initializeGraphics() {
  static byte graphics[] = {
    // Hero 1 — gun pointing RIGHT →
    B00110, B00110, B00000, B11111, B01110, B00110, B00110, B00110,  // Frame 1
    B00110, B00110, B00000, B11111, B01110, B00110, B00111, B01101,  // Frame 2
    B00110, B00110, B00000, B11111, B01110, B00110, B01011, B01001,  // Frame 3
    // Hero 2 — gun pointing LEFT ←
    B01100, B01100, B00000, B11111, B01110, B01100, B01100, B01100,  // Frame 4
    B01100, B01100, B00000, B11111, B01110, B01100, B11100, B10110,  // Frame 5
    B01100, B01100, B00000, B11111, B01110, B01100, B11010, B10010,  // Frame 6
  };

  lcd.createChar(1, &graphics[0]);
  lcd.createChar(2, &graphics[8]);
  lcd.createChar(3, &graphics[16]);
  lcd.createChar(4, &graphics[24]);
  lcd.createChar(5, &graphics[32]);
  lcd.createChar(6, &graphics[40]);

  for (int i = 0; i < TERRAIN_WIDTH; i++) {
    terrainUpper[i] = SPRITE_TERRAIN_EMPTY;
    terrainLower[i] = SPRITE_TERRAIN_EMPTY;
  }
}

// ============================================================
// GET HERO ROW
// ============================================================
byte getHeroRow(byte heroPos) {
  if (heroPos >= HERO_POSITION_JUMP_3 && heroPos <= HERO_POSITION_RUN_UPPER_3) {
    return 0;  // upper row
  }
  return 1;  // lower row
}

// ============================================================
// DRAW HEROES
// ============================================================
void drawHeroes(byte pos1, byte pos2) {
  // Clear terrain buffer
  for (int i = 0; i < TERRAIN_WIDTH; i++) {
    terrainUpper[i] = SPRITE_TERRAIN_EMPTY;
    terrainLower[i] = SPRITE_TERRAIN_EMPTY;
  }

  // ---- Hero 1 ----
  switch (pos1) {
    case HERO_POSITION_RUN_LOWER_1: terrainLower[HERO1_POSITION] = HERO1_RUN1; break;
    case HERO_POSITION_RUN_LOWER_2: terrainLower[HERO1_POSITION] = HERO1_RUN2; break;
    case HERO_POSITION_RUN_LOWER_3: terrainLower[HERO1_POSITION] = HERO1_RUN3; break;
    case HERO_POSITION_JUMP_1:
    case HERO_POSITION_JUMP_8:      terrainLower[HERO1_POSITION] = HERO1_RUN1; break;
    case HERO_POSITION_JUMP_2:
    case HERO_POSITION_JUMP_7:
      terrainUpper[HERO1_POSITION] = SPRITE_JUMP_UPPER;
      terrainLower[HERO1_POSITION] = HERO1_RUN2;
      break;
    case HERO_POSITION_JUMP_3:
    case HERO_POSITION_JUMP_4:
    case HERO_POSITION_JUMP_5:
    case HERO_POSITION_JUMP_6:      terrainUpper[HERO1_POSITION] = HERO1_RUN1; break;
    case HERO_POSITION_RUN_UPPER_1: terrainUpper[HERO1_POSITION] = HERO1_RUN1; break;
    case HERO_POSITION_RUN_UPPER_2: terrainUpper[HERO1_POSITION] = HERO1_RUN2; break;
    case HERO_POSITION_RUN_UPPER_3: terrainUpper[HERO1_POSITION] = HERO1_RUN3; break;
  }

  // ---- Hero 2 ----
  switch (pos2) {
    case HERO_POSITION_RUN_LOWER_1: terrainLower[HERO2_POSITION] = HERO2_RUN1; break;
    case HERO_POSITION_RUN_LOWER_2: terrainLower[HERO2_POSITION] = HERO2_RUN2; break;
    case HERO_POSITION_RUN_LOWER_3: terrainLower[HERO2_POSITION] = HERO2_RUN3; break;
    case HERO_POSITION_JUMP_1:
    case HERO_POSITION_JUMP_8:      terrainLower[HERO2_POSITION] = HERO2_RUN1; break;
    case HERO_POSITION_JUMP_2:
    case HERO_POSITION_JUMP_7:
      terrainUpper[HERO2_POSITION] = SPRITE_JUMP_UPPER;
      terrainLower[HERO2_POSITION] = HERO2_RUN2;
      break;
    case HERO_POSITION_JUMP_3:
    case HERO_POSITION_JUMP_4:
    case HERO_POSITION_JUMP_5:
    case HERO_POSITION_JUMP_6:      terrainUpper[HERO2_POSITION] = HERO2_RUN1; break;
    case HERO_POSITION_RUN_UPPER_1: terrainUpper[HERO2_POSITION] = HERO2_RUN1; break;
    case HERO_POSITION_RUN_UPPER_2: terrainUpper[HERO2_POSITION] = HERO2_RUN2; break;
    case HERO_POSITION_RUN_UPPER_3: terrainUpper[HERO2_POSITION] = HERO2_RUN3; break;
  }

  // ---- Draw bullets ----
  if (bullet01.active) {
    if (bullet01.row == 0) terrainUpper[bullet01.x] = BULLET_CHAR;
    else                   terrainLower[bullet01.x] = BULLET_CHAR;
  }
  if (bullet02.active) {
    if (bullet02.row == 0) terrainUpper[bullet02.x] = BULLET_CHAR;
    else                   terrainLower[bullet02.x] = BULLET_CHAR;
  }

  // ---- Print both rows — no flicker! ----
  terrainUpper[TERRAIN_WIDTH] = '\0';
  terrainLower[TERRAIN_WIDTH] = '\0';
  lcd.setCursor(0, 0);
  lcd.print(terrainUpper);
  lcd.setCursor(0, 1);
  lcd.print(terrainLower);
}

// ============================================================
// ADVANCE HERO STATE
// ============================================================
void advanceHero(byte &heroPos, volatile bool &jumpPushed) {
  if (jumpPushed && heroPos <= HERO_POSITION_RUN_LOWER_3) {
    heroPos = HERO_POSITION_JUMP_1;
    jumpPushed = false;
    return;
  }
  jumpPushed = false;

  if (heroPos == HERO_POSITION_RUN_LOWER_3) { heroPos = HERO_POSITION_RUN_LOWER_1; return; }
  if (heroPos == HERO_POSITION_RUN_UPPER_3) { heroPos = HERO_POSITION_RUN_UPPER_1; return; }
  if (heroPos == HERO_POSITION_JUMP_8)      { heroPos = HERO_POSITION_RUN_LOWER_1; return; }

  ++heroPos;
}

// ============================================================
// BULLET SYSTEM
// ============================================================
void spawnBullet(Bullet &bullet, byte heroPos, byte startX, int8_t dir) {
  if (!bullet.active) {
    bullet.active = true;
    bullet.x      = startX + dir;
    bullet.row    = getHeroRow(heroPos);
    bullet.dir    = dir;
  }
}

void moveBullet(Bullet &bullet) {
  if (!bullet.active) return;
  bullet.x += bullet.dir;
  if (bullet.x < 0 || bullet.x >= TERRAIN_WIDTH) {
    bullet.active = false;
  }
}

bool checkHit(Bullet &bullet, byte heroX, byte heroPos) {
  if (!bullet.active) return false;
  if (bullet.x == heroX && bullet.row == getHeroRow(heroPos)) {
    bullet.active = false;
    return true;
  }
  return false;
}

// ============================================================
// RESET BULLETS
// ============================================================
void resetBullets() {
  bullet01.x = -1; bullet01.row = 1; bullet01.dir = +1; bullet01.active = false;
  bullet02.x = -1; bullet02.row = 1; bullet02.dir = -1; bullet02.active = false;
}

// ============================================================
// GAME OVER
// ============================================================
void gameOver(const char* winner) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(winner);
  lcd.setCursor(0, 1);
  lcd.print("Press to restart");

  // Clear flags before waiting
  jumpPushed01 = false;
  jumpPushed02 = false;

  // Wait for either player to press jump
  while (!jumpPushed01 && !jumpPushed02);
  delay(300);
}

// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(115200);
  lcd.begin(16, 2);
  initializeGraphics();

  pinMode(BTN_JUMP_P1, INPUT_PULLUP);
  pinMode(BTN_JUMP_P2, INPUT_PULLUP);
  pinMode(BTN_FIRE_P1, INPUT_PULLUP);
  pinMode(BTN_FIRE_P2, INPUT_PULLUP);

  attachInterrupt(digitalPinToInterrupt(BTN_JUMP_P1), onJump01, FALLING);
  attachInterrupt(digitalPinToInterrupt(BTN_JUMP_P2), onJump02, FALLING);
  attachInterrupt(digitalPinToInterrupt(BTN_FIRE_P1), onFire01, FALLING);
  attachInterrupt(digitalPinToInterrupt(BTN_FIRE_P2), onFire02, FALLING);

  Serial.println("Setup complete!");
}

// ============================================================
// LOOP
// ============================================================
void loop() {
  static byte heroPos1 = HERO_POSITION_RUN_LOWER_1;
  static byte heroPos2 = HERO_POSITION_RUN_LOWER_1;
  static bool playing  = false;

  // ---- LOBBY ----
  if (!playing) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Player1 Player2");

    shown01 = false;
    shown02 = false;
    jumpPushed01 = false;
    jumpPushed02 = false;
    firePushed01 = false;
    firePushed02 = false;
    resetBullets();

    // Wait for both players ready
    while (!(shown01 && shown02)) {
      if (jumpPushed01 && !shown01) {
        lcd.setCursor(0, 1);
        lcd.print("Ready  ");
        shown01 = true;
        jumpPushed01 = false;
      }
      if (jumpPushed02 && !shown02) {
        lcd.setCursor(9, 1);
        lcd.print("Ready  ");
        shown02 = true;
        jumpPushed02 = false;
      }
    }

    delay(500);
    lcd.clear();
    initializeGraphics();
    heroPos1 = HERO_POSITION_RUN_LOWER_1;
    heroPos2 = HERO_POSITION_RUN_LOWER_1;
    playing  = true;
    return;
  }

  // ---- GAME RUNNING ----
  advanceHero(heroPos1, jumpPushed01);
  advanceHero(heroPos2, jumpPushed02);

  if (firePushed01) {
    spawnBullet(bullet01, heroPos1, HERO1_POSITION, +1);
    firePushed01 = false;
  }
  if (firePushed02) {
    spawnBullet(bullet02, heroPos2, HERO2_POSITION, -1);
    firePushed02 = false;
  }

  moveBullet(bullet01);
  moveBullet(bullet02);

  if (checkHit(bullet01, HERO2_POSITION, heroPos2)) {
    gameOver("Player 1 WINS!");
    playing = false;
    return;
  }
  if (checkHit(bullet02, HERO1_POSITION, heroPos1)) {
    gameOver("Player 2 WINS!");
    playing = false;
    return;
  }

  drawHeroes(heroPos1, heroPos2);
  delay(100);
}
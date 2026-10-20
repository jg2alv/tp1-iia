// sketch.js (CLIENTE) - usando GET em vez de POST

const ROWS = 6, COLS = 7;
const EMPTY = 0;

let gameStarted = false;
let cellSize = 80, margin = 16;
let board, turn = 1, winner = 0, aiThinking = false;
let players = { 1: "", 2: "" };

const API = "http://localhost:5001/";

// ------------------------- p5.js SETUP -------------------------
async function setup() 
{
  const w = COLS * cellSize + margin * 2;
  const h = ROWS * cellSize + margin * 2;
  let cnv = createCanvas(w, h);
  cnv.parent("mapCanvas");

  // Load AI players
  const url = `${API}/ai_players`;

  gameStarted = false;

  try {
    const response = await fetch(url);
    const data = await response.json();

    let player1Select = document.getElementById("player1");
    let player2Select = document.getElementById("player2");

    for(let p of data.players) 
    {
      console.log(p);

      const newOption1 = document.createElement('option');
      newOption1.value = p;
      newOption1.textContent = p;
      
      player1Select.appendChild(newOption1);

      const newOption2 = document.createElement('option');
      newOption2.value = p;
      newOption2.textContent = p;

      player2Select.appendChild(newOption2);
      gameStarted = true;
    }

    document.getElementById("newGame").onclick = newGame;
    newGame();
  } 
  catch (error) {
    console.error("Erro ao chamar a API ai_players:", error);
  } 

}

function draw() 
{
  background(255);
  drawGrid();

  if(gameStarted) {
    drawChips();
    updateHUD();
  }
}

function LoadPlayers() 
{
  const p1Select = document.getElementById("player1");
  const p2Select = document.getElementById("player2");
  
  players[1] = p1Select.value;
  players[2] = p2Select.value;

  if (winner === 0 && players[turn].slice(0, 2) === "AI") {
    makeAIMove();
  }
}

// ------------------------- UI & ESTADO -------------------------
function newGame() 
{
  board = Array.from({ length: ROWS }, () => Array(COLS).fill(EMPTY));
  
  LoadPlayers();
  
  turn = 1;
  winner = 0;
  
  aiThinking = false;
  if (players[turn].slice(0, 2) === "AI") {
    makeAIMove();
  }

  updateHUD();
  console.log("Novo jogo com jogadores:", players);
}

function updateHUD() 
{
  // Desabilitar interface se IA pensando
  document.getElementById("player1").disabled = aiThinking;
  document.getElementById("player2").disabled = aiThinking;
  document.getElementById("maxTimeMs").disabled = aiThinking;
  document.getElementById("newGame").disabled = aiThinking;
  document.getElementById("maxDepth").disabled = aiThinking;

  // Atualizar labels
  document.getElementById("turnLabel").innerText =
    winner !== 0 ? "—" :
    (turn === 1 ? (players[1] === "human" ? "P1 (vermelho)" : "IA P1 (vermelho)") :
                  (players[2] === "human" ? "P2 (amarelo)" : "IA P2 (amarelo)"));

  // Atualizar vencedor
  document.getElementById("winnerLabel").innerText = 
    winner === 0 ? "—" :
    winner === -1 ? "Empate!" :
    (winner === 1 ? "P1 (Vermelho)" : "P2 (Amarelo)") + " venceu!";
}

// ------------------------ DESENHO DO TABULEIRO ------------------------
function drawGrid() 
{
  push();
  translate(margin, margin);

  // Desenhar fundo azul
  noStroke();
  fill(30, 70, 200);
  rect(0, 0, COLS * cellSize, ROWS * cellSize, 14);

  // Desenhar círculos vazios
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      fill(240);
      circle(c * cellSize + cellSize / 2, r * cellSize + cellSize / 2, cellSize * 0.7);
    }
  }

  // Desenhar linhas de grade
  stroke(0, 50);
  strokeWeight(2);
  for (let r = 1; r < ROWS; r++) {
    line(0, r * cellSize, COLS * cellSize, r * cellSize);
  }
  for (let c = 1; c < COLS; c++) {
    line(c * cellSize, 0, c * cellSize, ROWS * cellSize);
  }

  // Highlight coluna sob o mouse se o turno for do jogador
  if (winner === 0 && players[turn] === "human" &&
      mouseX >= margin && mouseX <= width - margin &&
      mouseY >= margin && mouseY <= height - margin) {
    const col = Math.floor((mouseX - margin) / cellSize);
    if (col >= 0 && col < COLS) {
      noStroke();
      fill(255, 255, 255, 30);
      rect(col * cellSize, 0, cellSize, ROWS * cellSize);
    }
  }

  pop();
}

function drawChips() 
{
  push();
  translate(margin, margin);

  for (let r = 0; r < ROWS; r++) 
  {
    for (let c = 0; c < COLS; c++) 
    {
      const cell = board[r][c];
      
      if (cell === EMPTY) continue;

      if (cell === 1) 
      {
        fill(220, 50, 30);  // vermelho
      } 
      else if (cell === 2) 
      {
        fill(240, 220, 70); // amarelo
      }

      circle(c * cellSize + cellSize / 2, r * cellSize + cellSize / 2, cellSize * 0.7);
    }
  }
  
  pop();
}

function changeTurn() 
{
  turn = turn === 1 ? 2 : 1;

  if (winner === 0 && players[turn].slice(0, 2) === "AI") {
    makeAIMove();
  }
}

// ------------------------ ENTRADA DO JOGADOR ------------------------
function mousePressed() 
{
  if (winner !== 0) return;

  if (players[turn] === "human" && !aiThinking) 
  {
    // Limitar jogada ao canvas
    if (mouseX < margin || mouseX > width - margin ||
        mouseY < margin || mouseY > height - margin) {
      return;
    }

    // Calcular coluna clicada
    const col = Math.floor((mouseX - margin) / cellSize);
    if (col >= 0 && col < COLS) 
    {
      if (applyMove(col, turn)) 
      {
        checkWinner();
        changeTurn();
      }
    }
  }
}

function applyMove(col, player)
{
  if (col < 0 || col >= COLS || board[0][col] !== EMPTY) return false;
  
  for (let r = ROWS - 1; r >= 0; r--) 
  {
    if (board[r][col] === EMPTY) 
    {
      board[r][col] = player;
      return true;
    }
  }
  
  return false;
}

function checkWinner() 
{
  const w = winnerOf(board);
  
  if (w !== 0) 
  {
    winner = w;
  }
  else if (board[0].every(x => x !== EMPTY)) 
  {
    winner = -1;
  }
}

// ------------------------ LÓGICA DO SERVIDOR GET ------------------------
function encodeBoard(board) 
{
  return board.map(row => row.join('')).join(';');
}

async function makeAIMove() 
{
  if (winner !== 0 || aiThinking) return;
  
  aiThinking = true;

  const boardStr = encodeBoard(board);
  const player = players[turn];
  const maxTimeMs = parseInt(document.getElementById("maxTimeMs").value);
  const maxDepth = parseInt(document.getElementById("maxDepth").value);

  console.log(`Calling AI API with board=${boardStr}, player=${player}, turn=${turn}, max_time_ms=${maxTimeMs}, max_depth=${maxDepth}`);

  const url = `${API}/ai_move?board=${encodeURIComponent(boardStr)}&player=${encodeURIComponent(player)}&turn=${encodeURIComponent(turn)}&max_time_ms=${encodeURIComponent(maxTimeMs)}&max_depth=${encodeURIComponent(maxDepth)}`;

  try {
    const response = await fetch(url);
    const data = await response.json();
    
    const col = data.col;
    if (applyMove(col, turn)) {
      aiThinking = false;
      checkWinner();
      changeTurn();
    } else {
      aiThinking = false;
      console.error("Jogada inválida retornada pela IA:", col);
    }
  } 
  catch (error) {
    aiThinking = false;
    console.error("Erro ao chamar a API da IA:", error);
  } 
  finally  {
    aiThinking = false;
  }
  
}

// ------------------------ FUNÇÕES AUXILIARES ------------------------
function winnerOf(bd) 
{
  // horizontais
  for (let r = 0; r < ROWS; r++)
    for (let c = 0; c < COLS - 3; c++) {
      const x = bd[r][c];
      if (x && x === bd[r][c + 1] && x === bd[r][c + 2] && x === bd[r][c + 3]) return x;
    }

  // verticais
  for (let c = 0; c < COLS; c++)
    for (let r = 0; r < ROWS - 3; r++) {
      const x = bd[r][c];
      if (x && x === bd[r + 1][c] && x === bd[r + 2][c] && x === bd[r + 3][c]) return x;
    }

  // diag ↘
  for (let r = 0; r < ROWS - 3; r++)
    for (let c = 0; c < COLS - 3; c++) {
      const x = bd[r][c];
      if (x && x === bd[r + 1][c + 1] && x === bd[r + 2][c + 2] && x === bd[r + 3][c + 3]) return x;
    }

  // diag ↗
  for (let r = 3; r < ROWS; r++)
    for (let c = 0; c < COLS - 3; c++) {
      const x = bd[r][c];
      if (x && x === bd[r - 1][c + 1] && x === bd[r - 2][c + 2] && x === bd[r - 3][c + 3]) return x;
    }

  return 0;
}
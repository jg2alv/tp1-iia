from typing import List, Tuple, Optional, Dict
import time
import math
import random

ROWS, COLS = 6, 7
EMPTY, P1, P2 = 0, 1, 2

WIN_SCORE = 1_000_000
CENTER_WEIGHT = 6
MOVE_ORDER = (3, 2, 4, 1, 5, 0, 6)
MOVE_RANK = {col: rank for rank, col in enumerate(MOVE_ORDER)}

TT_EXACT = "EXACT"
TT_LOWER = "LOWER"
TT_UPPER = "UPPER"
TT_MAX_ENTRIES = 200_000

# Configuracao temporaria dos dois agentes exibidos pela interface.
# AI_Random usa PRIMARY_ALGORITHM; AI_Dummy usa SECONDARY_ALGORITHM.
PRIMARY_ALGORITHM = "competition"
SECONDARY_ALGORITHM = "alpha_beta"

BoardSignature = bytes
TranspositionKey = Tuple[BoardSignature, int, int, int]
TranspositionEntry = Tuple[int, str, Optional[int]]
PositionHintKey = Tuple[BoardSignature, int, int]

class SearchTimeout(Exception):
    """Sinaliza que o prazo interno da busca foi atingido."""

    pass

# -----------------------------------------------------------------------------
# Utilidades de tabuleiro (PRONTAS)
# -----------------------------------------------------------------------------
def copy_board(board: List[List[int]]) -> List[List[int]]:
    return [row[:] for row in board]

def valid_moves(board: List[List[int]]) -> List[int]:
    """Retorna as colunas ainda jogáveis (topo vazio)."""
    return [c for c in range(COLS) if board[0][c] == EMPTY]

def make_move(board: List[List[int]], col: int, player: int) -> Optional[List[List[int]]]:
    """Retorna um novo tabuleiro aplicando a gravidade na coluna col; None se inválido."""
    if col < 0 or col >= COLS or board[0][col] != EMPTY:
        return None
    nb = copy_board(board)
    for r in reversed(range(ROWS)):
        if nb[r][col] == EMPTY:
            nb[r][col] = player
            return nb
    return None

def winner(board: List[List[int]]) -> int:
    """0 se ninguém venceu; 1 ou 2 se há 4 em linha."""
    # Horizontais
    for r in range(ROWS):
        for c in range(COLS - 3):
            x = board[r][c]
            if x != EMPTY and x == board[r][c+1] == board[r][c+2] == board[r][c+3]:
                return x
    # Verticais
    for c in range(COLS):
        for r in range(ROWS - 3):
            x = board[r][c]
            if x != EMPTY and x == board[r+1][c] == board[r+2][c] == board[r+3][c]:
                return x
    # Diag ↘
    for r in range(ROWS - 3):
        for c in range(COLS - 3):
            x = board[r][c]
            if x != EMPTY and x == board[r+1][c+1] == board[r+2][c+2] == board[r+3][c+3]:
                return x
    # Diag ↗
    for r in range(3, ROWS):
        for c in range(COLS - 3):
            x = board[r][c]
            if x != EMPTY and x == board[r-1][c+1] == board[r-2][c+2] == board[r-3][c+3]:
                return x
    return 0

def is_full(board: List[List[int]]) -> bool:
    return all(board[0][c] != EMPTY for c in range(COLS))

def terminal(board: List[List[int]]) -> Tuple[bool, int]:
    """(é_terminal, vencedor) com vencedor=0 para empate/indefinido."""
    w = winner(board)
    if w != 0:
        return True, w
    if is_full(board):
        return True, 0
    return False, 0

def other(player: int) -> int:
    return P1 if player == P2 else P2

# -----------------------------------------------------------------------------
# Heuristica e Minimax com profundidade limitada
# -----------------------------------------------------------------------------
def ordered_valid_moves(board: List[List[int]]) -> List[int]:
    """Retorna as jogadas validas, priorizando as colunas centrais."""
    return [col for col in MOVE_ORDER if board[0][col] == EMPTY]

def build_deadline(start: float, max_time_ms: int) -> Optional[float]:
    """Cria um prazo monotonicamente crescente com margem para o retorno."""
    if max_time_ms <= 0:
        return None

    safety_ms = min(300.0, max_time_ms * 0.20)
    usable_time_ms = max(0.0, max_time_ms - safety_ms)
    return start + usable_time_ms / 1000.0

def check_deadline(deadline: Optional[float]) -> None:
    """Interrompe a busca quando o prazo interno e atingido."""
    if deadline is not None and time.perf_counter() >= deadline:
        raise SearchTimeout

def tactical_fallback_move(board: List[List[int]], player: int) -> int:
    """Escolhe vitoria, bloqueio imediato ou a coluna legal mais central."""
    legal = ordered_valid_moves(board)
    if not legal:
        return 0

    for col in legal:
        child = make_move(board, col, player)
        if child is not None and winner(child) == player:
            return col

    opponent = other(player)
    for col in legal:
        child = make_move(board, col, opponent)
        if child is not None and winner(child) == opponent:
            return col

    return legal[0]

def is_playable_cell(board: List[List[int]], row: int, col: int) -> bool:
    """Indica se uma casa vazia pode receber uma peca na proxima jogada."""
    return (
        board[row][col] == EMPTY
        and (row == ROWS - 1 or board[row + 1][col] != EMPTY)
    )

def score_window(
    board: List[List[int]],
    coordinates: List[Tuple[int, int]],
    maximizing_player: int,
) -> int:
    """Avalia uma janela de quatro casas da perspectiva do jogador MAX."""
    minimizing_player = other(maximizing_player)
    values = [board[row][col] for row, col in coordinates]

    maximizing_count = values.count(maximizing_player)
    minimizing_count = values.count(minimizing_player)
    empty_count = values.count(EMPTY)

    # Uma janela ocupada pelos dois jogadores nao pode mais formar um Ligue-4.
    if maximizing_count > 0 and minimizing_count > 0:
        return 0

    if maximizing_count == 1 and empty_count == 3:
        return 1
    if maximizing_count == 2 and empty_count == 2:
        return 10
    if maximizing_count == 3 and empty_count == 1:
        empty_index = values.index(EMPTY)
        row, col = coordinates[empty_index]
        return 500 if is_playable_cell(board, row, col) else 40

    if minimizing_count == 1 and empty_count == 3:
        return -1
    if minimizing_count == 2 and empty_count == 2:
        return -12
    if minimizing_count == 3 and empty_count == 1:
        empty_index = values.index(EMPTY)
        row, col = coordinates[empty_index]
        return -650 if is_playable_cell(board, row, col) else -50

    return 0

def evaluate_board(board: List[List[int]], maximizing_player: int) -> int:
    """Avalia um estado nao terminal da perspectiva do jogador MAX."""
    minimizing_player = other(maximizing_player)
    score = 0

    # A coluna central participa do maior numero de linhas vencedoras.
    for row in range(ROWS):
        if board[row][COLS // 2] == maximizing_player:
            score += CENTER_WEIGHT
        elif board[row][COLS // 2] == minimizing_player:
            score -= CENTER_WEIGHT

    # Janelas horizontais.
    for row in range(ROWS):
        for col in range(COLS - 3):
            coordinates = [(row, col + offset) for offset in range(4)]
            score += score_window(board, coordinates, maximizing_player)

    # Janelas verticais.
    for col in range(COLS):
        for row in range(ROWS - 3):
            coordinates = [(row + offset, col) for offset in range(4)]
            score += score_window(board, coordinates, maximizing_player)

    # Janelas diagonais descendentes.
    for row in range(ROWS - 3):
        for col in range(COLS - 3):
            coordinates = [(row + offset, col + offset) for offset in range(4)]
            score += score_window(board, coordinates, maximizing_player)

    # Janelas diagonais ascendentes.
    for row in range(3, ROWS):
        for col in range(COLS - 3):
            coordinates = [(row - offset, col + offset) for offset in range(4)]
            score += score_window(board, coordinates, maximizing_player)

    return score

def minimax(
    board: List[List[int]],
    remaining_depth: int,
    current_player: int,
    maximizing_player: int,
    stats: Dict[str, int],
) -> int:
    """Executa Minimax puro, sem poda, e retorna o valor do estado."""
    stats["states_visited"] += 1

    is_terminal, winning_player = terminal(board)
    if is_terminal:
        if winning_player == maximizing_player:
            return WIN_SCORE + remaining_depth
        if winning_player == other(maximizing_player):
            return -WIN_SCORE - remaining_depth
        return 0

    if remaining_depth == 0:
        return evaluate_board(board, maximizing_player)

    legal = ordered_valid_moves(board)

    if current_player == maximizing_player:
        value = -math.inf
        for col in legal:
            child = make_move(board, col, current_player)
            if child is not None:
                child_value = minimax(
                    child,
                    remaining_depth - 1,
                    other(current_player),
                    maximizing_player,
                    stats,
                )
                value = max(value, child_value)
        return int(value)

    value = math.inf
    for col in legal:
        child = make_move(board, col, current_player)
        if child is not None:
            child_value = minimax(
                child,
                remaining_depth - 1,
                other(current_player),
                maximizing_player,
                stats,
            )
            value = min(value, child_value)
    return int(value)

def alpha_beta(
    board: List[List[int]],
    remaining_depth: int,
    current_player: int,
    maximizing_player: int,
    alpha: float,
    beta: float,
    stats: Dict[str, int],
    deadline: Optional[float] = None,
) -> int:
    """Executa Minimax com poda Alfa-Beta e retorna o valor do estado."""
    check_deadline(deadline)
    stats["states_visited"] += 1

    is_terminal, winning_player = terminal(board)
    if is_terminal:
        if winning_player == maximizing_player:
            return WIN_SCORE + remaining_depth
        if winning_player == other(maximizing_player):
            return -WIN_SCORE - remaining_depth
        return 0

    if remaining_depth == 0:
        return evaluate_board(board, maximizing_player)

    legal = ordered_valid_moves(board)

    if current_player == maximizing_player:
        value = -math.inf
        for move_index, col in enumerate(legal):
            check_deadline(deadline)
            child = make_move(board, col, current_player)
            if child is None:
                continue

            child_value = alpha_beta(
                child,
                remaining_depth - 1,
                other(current_player),
                maximizing_player,
                alpha,
                beta,
                stats,
                deadline,
            )
            check_deadline(deadline)
            value = max(value, child_value)
            alpha = max(alpha, value)

            if alpha >= beta and move_index < len(legal) - 1:
                stats["cutoffs"] += 1
                break

        return int(value)

    value = math.inf
    for move_index, col in enumerate(legal):
        check_deadline(deadline)
        child = make_move(board, col, current_player)
        if child is None:
            continue

        child_value = alpha_beta(
            child,
            remaining_depth - 1,
            other(current_player),
            maximizing_player,
            alpha,
            beta,
            stats,
            deadline,
        )
        check_deadline(deadline)
        value = min(value, child_value)
        beta = min(beta, value)

        if beta <= alpha and move_index < len(legal) - 1:
            stats["cutoffs"] += 1
            break

    return int(value)

def search_root_minimax(
    board: List[List[int]],
    player: int,
    depth: int,
    stats: Dict[str, int],
) -> Tuple[int, int]:
    """Avalia completamente a raiz com Minimax puro."""
    stats["states_visited"] += 1
    legal = ordered_valid_moves(board)

    best_move = legal[0] if legal else 0
    best_score = -math.inf

    for col in legal:
        child = make_move(board, col, player)
        if child is None:
            continue

        score = minimax(
            child,
            depth - 1,
            other(player),
            player,
            stats,
        )
        if score > best_score:
            best_score = score
            best_move = col

    return best_move, int(best_score)

def search_root_alpha_beta(
    board: List[List[int]],
    player: int,
    depth: int,
    stats: Dict[str, int],
    deadline: Optional[float],
) -> Tuple[Optional[int], Optional[int], bool, int]:
    """Busca a raiz e preserva apenas filhos completamente avaliados."""
    try:
        check_deadline(deadline)
    except SearchTimeout:
        return None, None, False, 0

    stats["states_visited"] += 1
    legal = ordered_valid_moves(board)
    if not legal:
        return 0, 0, True, 0

    best_move: Optional[int] = None
    best_score = -math.inf
    alpha = -math.inf
    beta = math.inf
    completed_root_children = 0

    for col in legal:
        try:
            check_deadline(deadline)
            child = make_move(board, col, player)
            if child is None:
                continue

            score = alpha_beta(
                child,
                depth - 1,
                other(player),
                player,
                alpha,
                beta,
                stats,
                deadline,
            )
            check_deadline(deadline)
        except SearchTimeout:
            completed_score = None if best_move is None else int(best_score)
            return (
                best_move,
                completed_score,
                False,
                completed_root_children,
            )

        completed_root_children += 1
        if score > best_score:
            best_score = score
            best_move = col

        alpha = max(alpha, best_score)

    return best_move, int(best_score), True, completed_root_children

def iterative_deepening_search(
    board: List[List[int]],
    player: int,
    max_depth: int,
    fallback_move: int,
    stats: Dict[str, int],
    deadline: Optional[float],
) -> Tuple[int, Optional[int], int, int, bool]:
    """Aprofunda iterativamente e confirma apenas iteracoes completas."""
    best_move = fallback_move
    best_score: Optional[int] = None
    completed_depth = 0
    attempted_depth = 0
    timed_out = False

    for depth in range(1, max_depth + 1):
        attempted_depth = depth
        candidate_move, candidate_score, completed, _ = search_root_alpha_beta(
            board,
            player,
            depth,
            stats,
            deadline,
        )

        if not completed:
            timed_out = True
            break

        if candidate_move is not None and candidate_score is not None:
            best_move = candidate_move
            best_score = candidate_score
            completed_depth = depth

    return (
        best_move,
        best_score,
        completed_depth,
        attempted_depth,
        timed_out,
    )

# -----------------------------------------------------------------------------
# Busca para competicao: ID + Alfa-Beta + TT + ordenacao dinamica
# -----------------------------------------------------------------------------
def board_signature(board: List[List[int]]) -> BoardSignature:
    """Codifica o tabuleiro de forma imutavel e compacta para uso na TT."""
    return bytes(cell for row in board for cell in row)

def is_immediate_winning_move(
    board: List[List[int]],
    col: int,
    player: int,
) -> bool:
    """Testa uma vitoria na proxima jogada sem copiar o tabuleiro."""
    if col < 0 or col >= COLS or board[0][col] != EMPTY:
        return False

    row = ROWS - 1
    while row >= 0 and board[row][col] != EMPTY:
        row -= 1

    if row < 0:
        return False

    for row_step, col_step in ((0, 1), (1, 0), (1, 1), (1, -1)):
        connected = 1

        scan_row = row + row_step
        scan_col = col + col_step
        while (
            0 <= scan_row < ROWS
            and 0 <= scan_col < COLS
            and board[scan_row][scan_col] == player
        ):
            connected += 1
            scan_row += row_step
            scan_col += col_step

        scan_row = row - row_step
        scan_col = col - col_step
        while (
            0 <= scan_row < ROWS
            and 0 <= scan_col < COLS
            and board[scan_row][scan_col] == player
        ):
            connected += 1
            scan_row -= row_step
            scan_col -= col_step

        if connected >= 4:
            return True

    return False

def root_tactical_choice(
    board: List[List[int]],
    player: int,
) -> Tuple[Optional[int], Optional[str]]:
    """Detecta vitoria direta ou o unico bloqueio que evita derrota imediata."""
    legal = ordered_valid_moves(board)
    winning_moves = [
        col for col in legal if is_immediate_winning_move(board, col, player)
    ]
    if winning_moves:
        return winning_moves[0], "immediate_win"

    opponent = other(player)
    opponent_wins = [
        col for col in legal if is_immediate_winning_move(board, col, opponent)
    ]
    if len(opponent_wins) == 1:
        return opponent_wins[0], "forced_block"

    return None, None

def competition_ordered_children(
    board: List[List[int]],
    current_player: int,
    tt_move: Optional[int],
    previous_iteration_move: Optional[int],
    deadline: Optional[float],
) -> List[Tuple[int, List[List[int]]]]:
    """Gera cada filho uma vez e aplica a ordem tatica, TT, PV e centro."""
    legal = ordered_valid_moves(board)
    winning_columns = set()
    blocking_columns = set()
    children_by_column: Dict[int, List[List[int]]] = {}

    for col in legal:
        check_deadline(deadline)
        if is_immediate_winning_move(board, col, current_player):
            winning_columns.add(col)

        child = make_move(board, col, current_player)
        if child is not None:
            children_by_column[col] = child

    opponent = other(current_player)
    for col in legal:
        check_deadline(deadline)
        if is_immediate_winning_move(board, col, opponent):
            blocking_columns.add(col)

    ordered_columns: List[int] = []

    def append_once(col: Optional[int]) -> None:
        if (
            col is not None
            and col in children_by_column
            and col not in ordered_columns
        ):
            ordered_columns.append(col)

    for col in legal:
        if col in winning_columns:
            append_once(col)
    for col in legal:
        if col in blocking_columns:
            append_once(col)
    append_once(tt_move)
    append_once(previous_iteration_move)
    for col in legal:
        append_once(col)

    return [(col, children_by_column[col]) for col in ordered_columns]

def store_tt_entry(
    table: Dict[TranspositionKey, TranspositionEntry],
    key: TranspositionKey,
    entry: TranspositionEntry,
    stats: Dict[str, int],
    iteration_hints: Dict[PositionHintKey, int],
) -> None:
    """Armazena uma entrada sem deixar a tabela crescer indefinidamente."""
    existing = table.get(key)
    if existing is not None and existing[1] == TT_EXACT and entry[1] != TT_EXACT:
        return

    if existing is None and len(table) >= TT_MAX_ENTRIES:
        return

    table[key] = entry
    stats["tt_stores"] += 1
    stats["tt_peak_entries"] = max(stats["tt_peak_entries"], len(table))

    best_move = entry[2]
    if best_move is not None:
        signature, current_player, maximizing_player, _ = key
        iteration_hints[(signature, current_player, maximizing_player)] = best_move

def competition_alpha_beta(
    board: List[List[int]],
    remaining_depth: int,
    current_player: int,
    maximizing_player: int,
    alpha: float,
    beta: float,
    stats: Dict[str, int],
    deadline: Optional[float],
    table: Dict[TranspositionKey, TranspositionEntry],
    previous_hints: Dict[PositionHintKey, int],
    iteration_hints: Dict[PositionHintKey, int],
    allow_tt_bounds: bool = True,
) -> int:
    """Alfa-Beta com TT por iteracao e ordenacao de movimentos competitiva."""
    check_deadline(deadline)
    stats["states_visited"] += 1

    signature = board_signature(board)
    key = (signature, current_player, maximizing_player, remaining_depth)
    hint_key = (signature, current_player, maximizing_player)
    original_alpha = alpha
    original_beta = beta
    tt_move: Optional[int] = None

    cached = table.get(key)
    if cached is not None:
        cached_value, cached_flag, tt_move = cached
        stats["tt_hits"] += 1

        if cached_flag == TT_EXACT:
            stats["tt_exact_hits"] += 1
            return cached_value

        if allow_tt_bounds:
            if cached_flag == TT_LOWER:
                alpha = max(alpha, cached_value)
            elif cached_flag == TT_UPPER:
                beta = min(beta, cached_value)

            if alpha >= beta:
                stats["tt_cutoffs"] += 1
                return cached_value

    is_terminal, winning_player = terminal(board)
    if is_terminal:
        if winning_player == maximizing_player:
            value = WIN_SCORE + remaining_depth
        elif winning_player == other(maximizing_player):
            value = -WIN_SCORE - remaining_depth
        else:
            value = 0

        store_tt_entry(
            table,
            key,
            (value, TT_EXACT, None),
            stats,
            iteration_hints,
        )
        return value

    if remaining_depth == 0:
        value = evaluate_board(board, maximizing_player)
        store_tt_entry(
            table,
            key,
            (value, TT_EXACT, None),
            stats,
            iteration_hints,
        )
        return value

    stats["states_expanded"] += 1
    children = competition_ordered_children(
        board,
        current_player,
        tt_move,
        previous_hints.get(hint_key),
        deadline,
    )

    if not children:
        store_tt_entry(
            table,
            key,
            (0, TT_EXACT, None),
            stats,
            iteration_hints,
        )
        return 0

    best_move: Optional[int] = None

    if current_player == maximizing_player:
        value = -math.inf
        for child_index, (col, child) in enumerate(children):
            child_value = competition_alpha_beta(
                child,
                remaining_depth - 1,
                other(current_player),
                maximizing_player,
                alpha,
                beta,
                stats,
                deadline,
                table,
                previous_hints,
                iteration_hints,
                allow_tt_bounds,
            )
            check_deadline(deadline)

            if (
                child_value > value
                or (
                    child_value == value
                    and (
                        best_move is None
                        or MOVE_RANK[col] < MOVE_RANK[best_move]
                    )
                )
            ):
                value = child_value
                best_move = col

            alpha = max(alpha, value)
            if alpha >= beta:
                if child_index < len(children) - 1:
                    stats["cutoffs"] += 1
                break
    else:
        value = math.inf
        for child_index, (col, child) in enumerate(children):
            child_value = competition_alpha_beta(
                child,
                remaining_depth - 1,
                other(current_player),
                maximizing_player,
                alpha,
                beta,
                stats,
                deadline,
                table,
                previous_hints,
                iteration_hints,
                allow_tt_bounds,
            )
            check_deadline(deadline)

            if (
                child_value < value
                or (
                    child_value == value
                    and (
                        best_move is None
                        or MOVE_RANK[col] < MOVE_RANK[best_move]
                    )
                )
            ):
                value = child_value
                best_move = col

            beta = min(beta, value)
            if beta <= alpha:
                if child_index < len(children) - 1:
                    stats["cutoffs"] += 1
                break

    check_deadline(deadline)
    value = int(value)
    if value <= original_alpha:
        flag = TT_UPPER
    elif value >= original_beta:
        flag = TT_LOWER
    else:
        flag = TT_EXACT

    store_tt_entry(
        table,
        key,
        (value, flag, best_move),
        stats,
        iteration_hints,
    )
    return value

def search_root_competition(
    board: List[List[int]],
    player: int,
    depth: int,
    stats: Dict[str, int],
    deadline: Optional[float],
    table: Dict[TranspositionKey, TranspositionEntry],
    previous_hints: Dict[PositionHintKey, int],
    iteration_hints: Dict[PositionHintKey, int],
) -> Tuple[Optional[int], Optional[int], bool, int]:
    """Busca uma iteracao completa e resolve empates pela ordem canonica."""
    try:
        check_deadline(deadline)
    except SearchTimeout:
        return None, None, False, 0

    stats["states_visited"] += 1
    legal = ordered_valid_moves(board)
    if not legal:
        return 0, 0, True, 0

    signature = board_signature(board)
    root_key = (signature, player, player, depth)
    root_hint_key = (signature, player, player)
    stats["states_expanded"] += 1

    try:
        children = competition_ordered_children(
            board,
            player,
            None,
            previous_hints.get(root_hint_key),
            deadline,
        )
    except SearchTimeout:
        return None, None, False, 0

    best_move: Optional[int] = None
    best_score = -math.inf
    alpha = -math.inf
    beta = math.inf
    completed_root_children = 0

    for col, child in children:
        try:
            score = competition_alpha_beta(
                child,
                depth - 1,
                other(player),
                player,
                alpha,
                beta,
                stats,
                deadline,
                table,
                previous_hints,
                iteration_hints,
            )
            check_deadline(deadline)

            # Com uma janela Alfa-Beta estreita, um empate pode ser apenas um
            # limite. Rebusca com janela completa antes de trocar para uma
            # coluna de maior prioridade canonica.
            if (
                score == best_score
                and best_move is not None
                and MOVE_RANK[col] < MOVE_RANK[best_move]
            ):
                score = competition_alpha_beta(
                    child,
                    depth - 1,
                    other(player),
                    player,
                    -math.inf,
                    math.inf,
                    stats,
                    deadline,
                    table,
                    previous_hints,
                    iteration_hints,
                    allow_tt_bounds=False,
                )
                check_deadline(deadline)
        except SearchTimeout:
            completed_score = None if best_move is None else int(best_score)
            return (
                best_move,
                completed_score,
                False,
                completed_root_children,
            )

        completed_root_children += 1
        if (
            score > best_score
            or (
                score == best_score
                and (
                    best_move is None
                    or MOVE_RANK[col] < MOVE_RANK[best_move]
                )
            )
        ):
            best_score = score
            best_move = col

        alpha = max(alpha, best_score)

    try:
        check_deadline(deadline)
    except SearchTimeout:
        return best_move, int(best_score), False, completed_root_children

    store_tt_entry(
        table,
        root_key,
        (int(best_score), TT_EXACT, best_move),
        stats,
        iteration_hints,
    )
    if best_move is not None:
        iteration_hints[root_hint_key] = best_move
    return best_move, int(best_score), True, completed_root_children

def competition_iterative_deepening_search(
    board: List[List[int]],
    player: int,
    max_depth: int,
    fallback_move: int,
    stats: Dict[str, int],
    deadline: Optional[float],
) -> Tuple[int, Optional[int], int, int, bool]:
    """ID competitivo; TT e dicas so sao promovidas apos iteracao completa."""
    best_move = fallback_move
    best_score: Optional[int] = None
    completed_depth = 0
    attempted_depth = 0
    timed_out = False
    previous_hints: Dict[PositionHintKey, int] = {}

    for depth in range(1, max_depth + 1):
        attempted_depth = depth
        iteration_table: Dict[TranspositionKey, TranspositionEntry] = {}
        iteration_hints: Dict[PositionHintKey, int] = {}
        candidate_move, candidate_score, completed, _ = (
            search_root_competition(
                board,
                player,
                depth,
                stats,
                deadline,
                iteration_table,
                previous_hints,
                iteration_hints,
            )
        )

        if not completed:
            timed_out = True
            break

        if candidate_move is not None and candidate_score is not None:
            best_move = candidate_move
            best_score = candidate_score
            completed_depth = depth
            previous_hints = iteration_hints

    return (
        best_move,
        best_score,
        completed_depth,
        attempted_depth,
        timed_out,
    )

# -----------------------------------------------------------------------------
# ÚNICO PONTO A SER IMPLEMENTADO PELOS ALUNOS
# -----------------------------------------------------------------------------
def choose_move(board: List[List[int]], turn: int, config: Dict) -> Tuple[int, Dict]:
    """
    Decide a coluna (0..6) para jogar agora.

    Parâmetros:
      - board: matriz 6x7 com valores {0,1,2}
      - turn: 1 ou 2
      - config: {"max_time_ms": int, "max_depth": int,
                 "algorithm": "minimax" | "alpha_beta" |
                              "iterative_deepening" | "competition" (opcional)}

    Retorna:
      - col: int (0..6)
    """
    start = time.perf_counter()
    max_time_ms = int(config.get("max_time_ms"))
    max_depth = max(1, int(config.get("max_depth")))
    algorithm = str(config.get("algorithm", PRIMARY_ALGORITHM)).lower()
    turn = int(turn)

    if algorithm not in (
        "minimax",
        "alpha_beta",
        "iterative_deepening",
        "competition",
    ):
        raise ValueError(
            f"Algoritmo desconhecido: {algorithm}. "
            "Use 'minimax', 'alpha_beta', 'iterative_deepening' "
            "ou 'competition'."
        )
    legal = ordered_valid_moves(board)

    if not legal:
        # Sem jogadas: devolve 0 por convenção (servidor lida com isso)
        return 0

    empty_cells = sum(cell == EMPTY for row in board for cell in row)
    depth_limit = min(max_depth, empty_cells)
    deadline = build_deadline(start, max_time_ms)
    fallback = tactical_fallback_move(board, turn)
    stats = {
        "states_visited": 0,
        "states_expanded": 0,
        "cutoffs": 0,
        "tt_hits": 0,
        "tt_exact_hits": 0,
        "tt_cutoffs": 0,
        "tt_stores": 0,
        "tt_peak_entries": 0,
    }

    print(
        f"AI choose_move called with max_time_ms={max_time_ms}, "
        f"max_depth={max_depth}, depth_limit={depth_limit}, "
        f"player={turn}, algorithm={algorithm}"
    )

    if algorithm == "minimax":
        move, score = search_root_minimax(
            board,
            turn,
            depth_limit,
            stats,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        print(
            f"Minimax chose column {move} with score={score}, "
            f"depth={depth_limit}, states_visited={stats['states_visited']}, "
            f"cutoffs={stats['cutoffs']}, elapsed_ms={elapsed_ms:.3f}"
        )
        return move

    if algorithm == "alpha_beta":
        candidate_move, score, search_completed, completed_children = (
            search_root_alpha_beta(
                board,
                turn,
                depth_limit,
                stats,
                deadline,
            )
        )
        move = fallback if candidate_move is None else candidate_move
        score_text = "fallback" if score is None else str(score)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        print(
            f"AlphaBeta chose column {move} with score={score_text}, "
            f"target_depth={depth_limit}, search_completed={search_completed}, "
            f"root_children_completed={completed_children}, "
            f"states_visited={stats['states_visited']}, "
            f"cutoffs={stats['cutoffs']}, timed_out={not search_completed}, "
            f"elapsed_ms={elapsed_ms:.3f}"
        )
        return move

    if algorithm == "competition":
        tactical_move, tactical_reason = root_tactical_choice(board, turn)
        if tactical_move is not None:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            print(
                f"Competition chose column {tactical_move} "
                f"with score={tactical_reason}, completed_depth=0, "
                f"attempted_depth=0, states_visited=0, states_expanded=0, "
                f"cutoffs=0, tt_hits=0, tt_exact_hits=0, tt_cutoffs=0, "
                f"tt_stores=0, tt_peak_entries=0, timed_out=False, "
                f"elapsed_ms={elapsed_ms:.3f}"
            )
            return tactical_move

        move, score, completed_depth, attempted_depth, timed_out = (
            competition_iterative_deepening_search(
                board,
                turn,
                depth_limit,
                fallback,
                stats,
                deadline,
            )
        )
        score_text = "fallback" if score is None else str(score)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        print(
            f"Competition chose column {move} with score={score_text}, "
            f"completed_depth={completed_depth}, attempted_depth={attempted_depth}, "
            f"states_visited={stats['states_visited']}, "
            f"states_expanded={stats['states_expanded']}, "
            f"cutoffs={stats['cutoffs']}, tt_hits={stats['tt_hits']}, "
            f"tt_exact_hits={stats['tt_exact_hits']}, "
            f"tt_cutoffs={stats['tt_cutoffs']}, tt_stores={stats['tt_stores']}, "
            f"tt_peak_entries={stats['tt_peak_entries']}, "
            f"timed_out={timed_out}, elapsed_ms={elapsed_ms:.3f}"
        )
        return move

    move, score, completed_depth, attempted_depth, timed_out = (
        iterative_deepening_search(
            board,
            turn,
            depth_limit,
            fallback,
            stats,
            deadline,
        )
    )
    score_text = "fallback" if score is None else str(score)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    print(
        f"IterativeDeepening chose column {move} with score={score_text}, "
        f"completed_depth={completed_depth}, attempted_depth={attempted_depth}, "
        f"states_visited={stats['states_visited']}, "
        f"cutoffs={stats['cutoffs']}, timed_out={timed_out}, "
        f"elapsed_ms={elapsed_ms:.3f}"
    )
    return move

def choose_move_infinity(board: List[List[int]], turn: int, config: Dict) -> Tuple[int, Dict]:
    """
    Decide a coluna (0..6) para jogar agora.

    Parâmetros:
      - board: matriz 6x7 com valores {0,1,2}
      - turn: 1 ou 2
      - config: {"max_time_ms": int, "max_depth": int}

    Retorna:
      - col: int (0..6)
    """
    if SECONDARY_ALGORITHM == "random":
        start = time.perf_counter()
        legal = valid_moves(board)
        move = random.choice(legal) if legal else 0
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        print(
            f"Random chose column {move}, states_visited=0, "
            f"elapsed_ms={elapsed_ms:.3f}"
        )
        return move

    secondary_config = dict(config)
    secondary_config["algorithm"] = SECONDARY_ALGORITHM
    return choose_move(board, turn, secondary_config)

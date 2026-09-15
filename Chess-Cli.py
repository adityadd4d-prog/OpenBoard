import sys
import re

import chess

def main():
    board = chess.Board()

    while True:

        display_board_state(board)

        # Handling Default cases where the game ends
        if outcome := board.outcome(claim_draw=True):
            res = ("White Won" if outcome.winner else "Black Won") if outcome.winner is not None else "Draw"
            print(f"Result : {res} By {outcome.termination.name}")
            break


        # Handling Resignation of Players and Taking Validated Moves
        resign = None
        while True:
            move = input(f"{"White" if board.turn else "Black"} Turn | Enter Move Or Resign : ").lower()

            match move:
                case "quit" | "q":
                    sys.exit("Game Exited...")
                case "resign" | "res" | "r":
                    print(f"{"White" if not board.turn else "Black"} Won By Resignation.")
                    resign = board.turn
                    break
                case _:
                    try:
                        move = check_pawn_promotion(board, move)
                        validated_move = board.parse_uci(move)
                        board.push(validated_move)
                        break
                    except ValueError:
                        print("Invalid Move !!!")

        if resign is not None:
            break

def display_board_state(board):
    print(f"\n{board}\n")
    print(f"Total Moves Played : {len(board.move_stack)}")
    temp = chess.Board()
    print(f"Moves : {temp.variation_san(board.move_stack)}")
    if board.is_check():
        print("Check !")

# Handles If Promotion Of a Pawn Is Possible
def check_pawn_promotion(board, move):
    if  match := re.search("^([a-h][1-8])([a-h][1-8])([rbnq]?)$", move):
        pie = board.piece_at(chess.parse_square(match.group(1)))
        if pie is None:
            raise ValueError
        if match.group(3) != "":
            return move
        if pie.piece_type == chess.PAWN:
            if match.group(2)[1] in ["8", "1"]:
                if ( pro := input("Promote Piece To [r/n/b/q] : ").lower()) in ["r", "n", "b", "q"]:
                    return move + pro
                else:
                    return move + "q"
            else:
                return move
        else:
            return move
    else:
        raise ValueError


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nProgram Exited")

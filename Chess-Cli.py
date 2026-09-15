import sys

import chess

def main():
    board = chess.Board()

    while True:

        # Handling Default cases where the game ends
        if outcome := board.outcome(claim_draw=True):
            res = ("White Won" if outcome.winner else "Black Won") if outcome.winner is not None else "Draw"
            print(f"Result : {res} By {outcome.termination.name}")
            break

        print(f"\n{board}\n")

        # For Handling Resignation of Players and Taking Validated Moves
        resign = None
        while True:
            move = input(f"{"White" if board.turn else "Black"} Turn | Enter Move Or Resign : ").lower()
            if move in ["resign", "res", "r"]:
                print(f"{"White" if not board.turn else "Black"} Won By Resignation.")
                resign = board.turn
                break
            try:
                validated_move = board.parse_uci(move)
                board.push(validated_move)
                break
            except ValueError:
                print("Invalid Move !!!")

        if resign is not None:
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("Program Exited")





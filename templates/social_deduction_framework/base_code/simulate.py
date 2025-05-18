import random


def simulate_game(rules, num_games=10):
    """Run a very simple social deduction game simulation.

    Parameters
    ----------
    rules : dict
        Dictionary containing game parameters like number of players and imposters.
    num_games : int
        Number of simulations to run.

    Returns
    -------
    dict
        Dictionary with average win rate and average number of turns.
    """
    num_players = int(rules.get("num_players", 4))
    imposters = int(rules.get("imposters", 1))
    win_count = 0
    total_turns = 0
    for _ in range(num_games):
        turns = random.randint(5, 15)
        total_turns += turns
        # Imposters win with probability proportional to their number
        if random.random() < imposters / float(num_players):
            win_count += 1
    return {
        "win_rate": win_count / float(num_games),
        "avg_turns": total_turns / float(num_games),
    }


if __name__ == "__main__":
    example_rules = {"num_players": 5, "imposters": 1}
    print(simulate_game(example_rules))

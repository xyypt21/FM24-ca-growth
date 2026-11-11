"""Pick ACA and APA first/second/third 4-3-3 lineups with scipy's solver.

For each metric (ACA, APA), scipy assigns players to the 11 formation slots.
The best XI is selected first, then the same solver picks the second XI from the
remaining players. The third squad fills the remaining depth targets.

APA projects CA to ``max_age``, capped by PA and by ``apa_shortfall_years``:

    ca_after_years(ca, years) = round(ca + monthly_gain * 12 * years)

    age >= max_age: APA = CA
    age <  max_age: APA = min(PA,
                              ca_after_years(CA, max_age - age),
                              ca_after_years(CA, apa_shortfall_years))

ACA adds ``aca_growth_years`` of growth, capped by the age cap and APA:

    age >= max_age: ACA = CA
    age <  max_age: ACA = max(
        CA, min(ca_after_years(CA, aca_growth_years), cap, APA))

The sell list lives in ``fm24_sell``. Agreed incoming players are added and
agreed outgoing players are removed by ``fm24_transfers``.

Run:

    python src/fm24_lineup.py

It runs once and prints the lineups to the console. The game must be running
with a save loaded.
"""

from __future__ import annotations

from scipy.optimize import linear_sum_assignment

from fm24_ca_growth import growth_cap
from fm24_config import GrowthSettings, load_config, load_growth_settings
from fm24_memory import Memory
from fm24_players import Player, all_players
from fm24_transfers import with_transfers

# 4-3-3: one goalkeeper, four defenders, three midfielders, three forwards.
SLOTS = (
    "GK",
    "DL",
    "DC",
    "DC",
    "DR",
    "DM",
    "DM",
    "AML",
    "AMC",
    "AMR",
    "ST",
)
METRICS = ("aca", "apa")
# Third-squad depth: how many players must be able to play each position.
DEPTH = {
    "GK": 2,
    "DL": 4,
    "DC": 6,
    "DR": 4,
    "DM": 6,
    "AML": 4,
    "AMC": 4,
    "AMR": 4,
    "ST": 4,
}
FORBIDDEN = 10**9


def select_lineup(
    players: list[Player], metric: str, slots: tuple[str, ...] = SLOTS
) -> list[tuple[str, Player]]:
    """Return the best XI for one metric (``aca`` or ``apa``)."""
    if len(players) < len(slots):
        raise RuntimeError(
            f"Only {len(players)} players found; need at least {len(slots)}"
        )

    costs = [
        [
            -player[metric] if slot in player["positions"] else FORBIDDEN
            for slot in slots
        ]
        for player in players
    ]
    player_rows, slot_columns = linear_sum_assignment(costs)

    lineup: list[tuple[str, Player]] = []
    for player_row, slot_column in zip(player_rows, slot_columns, strict=True):
        if costs[player_row][slot_column] >= FORBIDDEN:
            raise RuntimeError(f"No eligible player left for {slots[slot_column]}")
        lineup.append((slots[slot_column], players[player_row]))
    return sorted(lineup, key=lambda entry: slots.index(entry[0]))


def ca_after_years(ca: int, years: float, settings: GrowthSettings) -> int:
    """Return CA after ``years`` of monthly gains, rounded to an integer."""
    return round(ca + settings.monthly_gain * 12 * years)


def predict_apa(player: Player, settings: GrowthSettings) -> int:
    """Project CA to max_age, capped by PA and by a configured growth span.

    The max_age projection can promise more than ``apa_shortfall_years`` of
    growth. When even that span cannot reach PA, ``ca_at_growth_limit`` wins.
    """
    age = player["age"]
    ca = player["ca"]
    if age is None or age >= settings.max_age:
        return ca
    ca_at_max_age = ca_after_years(ca, settings.max_age - age, settings)
    ca_at_growth_limit = ca_after_years(ca, settings.apa_shortfall_years, settings)
    return min(player["pa"], ca_at_max_age, ca_at_growth_limit)


def predict_aca(player: Player, settings: GrowthSettings) -> int:
    """CA plus configured growth, capped by cap and APA, never below CA."""
    age = player["age"]
    ca = player["ca"]
    if age is None or age >= settings.max_age:
        return ca
    cap = growth_cap(age, player["pa"], settings.cap)
    ca_after_aca_growth = ca_after_years(ca, settings.aca_growth_years, settings)
    aca = min(ca_after_aca_growth, cap, predict_apa(player, settings))
    return max(ca, aca)


def fill_third(
    players: list[Player],
    selected: list[tuple[str, Player]],
    metric: str,
) -> list[tuple[str, Player]]:
    """Fill a third squad until every DEPTH target is met.

    Remaining players are scanned from highest metric to lowest. A versatile
    player counts towards every position they can play, but joins the squad
    only once.
    """
    covered = {slot: 0 for slot in DEPTH}
    for _, player in selected:
        for position in player["positions"]:
            if position in covered:
                covered[position] += 1

    taken = {id(player) for _, player in selected}
    third: list[tuple[str, Player]] = []
    for player in sorted(
        (player for player in players if id(player) not in taken),
        key=lambda item: item[metric],
        reverse=True,
    ):
        if all(covered[slot] >= DEPTH[slot] for slot in DEPTH):
            break
        gaps = [
            slot
            for slot in DEPTH
            if slot in player["positions"] and covered[slot] < DEPTH[slot]
        ]
        if not gaps:
            continue
        for position in player["positions"]:
            if position in covered:
                covered[position] += 1
        third.append((gaps[0], player))

    missing = [
        f"{slot} {covered[slot]}/{DEPTH[slot]}"
        for slot in DEPTH
        if covered[slot] < DEPTH[slot]
    ]
    if missing:
        raise RuntimeError("Third XI cannot reach depth: " + ", ".join(missing))
    return third


def prepare_players(players: list[Player], settings: GrowthSettings) -> list[Player]:
    """Drop loaned players and add the ``aca``/``apa`` fields."""
    available = [player for player in players if not player.get("loan")]
    return [
        {
            **player,
            "apa": predict_apa(player, settings),
            "aca": predict_aca(player, settings),
        }
        for player in available
    ]


def build_lineups(
    players: list[Player], settings: GrowthSettings
) -> list[tuple[str, list[tuple[str, Player]]]]:
    """Return ACA/APA first/second/third lineups."""
    enriched = prepare_players(players, settings)
    lineups: list[tuple[str, list[tuple[str, Player]]]] = []
    for metric in METRICS:
        first = select_lineup(enriched, metric)
        used = {id(player) for _, player in first}
        remaining = [player for player in enriched if id(player) not in used]
        try:
            second = select_lineup(remaining, metric)
        except RuntimeError as error:
            raise RuntimeError(f"{metric.upper()} Second XI: {error}") from error
        try:
            third = fill_third(enriched, first + second, metric)
        except RuntimeError as error:
            raise RuntimeError(f"{metric.upper()} Third XI: {error}") from error

        lineups.append((f"{metric.upper()} First XI", first))
        lineups.append((f"{metric.upper()} Second XI", second))
        lineups.append((f"{metric.upper()} Third XI", third))
    return lineups


def format_lineups(
    lineups: list[tuple[str, list[tuple[str, Player]]]],
) -> str:
    """Format every lineup as plain text."""
    lines: list[str] = []
    for label, lineup in lineups:
        lines.append(label)
        lines.append(
            f"{'Slot':<5}{'Name':<28}{'Age':>5}{'CA':>4}{'ACA':>5}{'APA':>5}  Positions"
        )
        for slot, player in lineup:
            age = player["age"]
            age_text = "-" if age is None else f"{age:.1f}"
            positions = "/".join(player["positions"]) or "-"
            lines.append(
                f"{slot:<5}{str(player['name']):<28}{age_text:>5}"
                f"{player['ca']:>4}{player['aca']:>5}{player['apa']:>5}  {positions}"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def main() -> int:
    """Print the lineups once."""
    config = load_config()
    settings = load_growth_settings()
    try:
        with Memory.open(config) as memory:
            players = with_transfers(memory, all_players(memory))
        print(format_lineups(build_lineups(players, settings)))
    except RuntimeError as error:
        print(f"Error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

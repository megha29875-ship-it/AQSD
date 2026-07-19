"""
AQSD
Option Intelligence

Module: wall_engine.py
Version: 1.0
Author: AQSD

Description:
Detects important Call and Put option walls.

Outputs:
- Positional Call Wall
- Positional Put Wall
- Fresh Call Wall
- Fresh Put Wall
- Secondary Walls
- Wall Distance from Spot
- Wall Strength
- Wall Shift
- Expected Trading Range
- Breakout and Breakdown Watch
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from Scripts.option_intelligence.option_chain_loader import (
    OptionChainData,
    load_option_chain,
)

from Scripts.option_intelligence.exporters import (
    EngineResult,
    ExportMetadata,
    export_results,
    print_export_report,
)

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "Output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# DATA MODEL
# ============================================================

@dataclass(slots=True)
class WallResult:
    spot_price: float
    atm_strike: float
    strike_step: float

    positional_call_wall: float | None
    positional_call_wall_oi: float
    secondary_call_wall: float | None
    secondary_call_wall_oi: float

    positional_put_wall: float | None
    positional_put_wall_oi: float
    secondary_put_wall: float | None
    secondary_put_wall_oi: float

    fresh_call_wall: float | None
    fresh_call_wall_change_oi: float

    fresh_put_wall: float | None
    fresh_put_wall_change_oi: float

    call_wall_distance: float | None
    put_wall_distance: float | None

    call_wall_strength: str
    put_wall_strength: str

    expected_range_low: float | None
    expected_range_high: float | None
    expected_range_width: float | None

    call_wall_shift: str
    put_wall_shift: str
    combined_wall_shift: str

    range_bias: str
    breakout_watch: str
    breakdown_watch: str
    interpretation: str

    number_of_strikes: int
    timestamp: str


# ============================================================
# HELPERS
# ============================================================

def safe_top_row(
    dataframe: pd.DataFrame,
    value_column: str,
    rank: int = 1,
) -> pd.Series | None:
    """
    Return the selected ranked row based on a value column.
    """

    if dataframe.empty:
        return None

    ranked = dataframe.sort_values(
        value_column,
        ascending=False,
    ).reset_index(drop=True)

    row_index = rank - 1

    if row_index >= len(ranked):
        return None

    return ranked.iloc[row_index]


def optional_float(
    row: pd.Series | None,
    column: str,
) -> float | None:
    """
    Extract an optional float from a pandas row.
    """

    if row is None:
        return None

    value = row.get(column)

    if pd.isna(value):
        return None

    return float(value)


def calculate_wall_strength(
    primary_value: float,
    secondary_value: float,
) -> str:
    """
    Measure concentration at the primary wall.

    A large difference between the first and second wall
    indicates stronger concentration.
    """

    if primary_value <= 0:
        return "NO WALL"

    if secondary_value <= 0:
        return "VERY STRONG"

    ratio = primary_value / secondary_value

    if ratio >= 1.75:
        return "VERY STRONG"

    if ratio >= 1.35:
        return "STRONG"

    if ratio >= 1.10:
        return "MODERATE"

    return "WEAK"


# ============================================================
# WALL TABLE
# ============================================================

def build_wall_table(
    option_chain_data: OptionChainData,
) -> pd.DataFrame:
    """
    Aggregate Call and Put OI at every strike.
    """

    option_chain = option_chain_data.option_chain.copy()

    calls = (
        option_chain[
            option_chain["option_type"] == "CE"
        ]
        .groupby("strike", as_index=False)
        .agg(
            call_oi=("open_interest", "sum"),
            call_change_oi=("change_in_oi", "sum"),
            call_volume=("volume", "sum"),
        )
    )

    puts = (
        option_chain[
            option_chain["option_type"] == "PE"
        ]
        .groupby("strike", as_index=False)
        .agg(
            put_oi=("open_interest", "sum"),
            put_change_oi=("change_in_oi", "sum"),
            put_volume=("volume", "sum"),
        )
    )

    wall_table = pd.merge(
        calls,
        puts,
        on="strike",
        how="outer",
    ).fillna(0.0)

    wall_table["distance_from_spot"] = (
        wall_table["strike"]
        - option_chain_data.spot_price
    )

    wall_table["absolute_distance_from_spot"] = (
        wall_table["distance_from_spot"].abs()
    )

    wall_table["call_oi_share_percent"] = (
        wall_table["call_oi"]
        / max(wall_table["call_oi"].sum(), 1.0)
        * 100.0
    )

    wall_table["put_oi_share_percent"] = (
        wall_table["put_oi"]
        / max(wall_table["put_oi"].sum(), 1.0)
        * 100.0
    )

    return wall_table.sort_values(
        "strike"
    ).reset_index(drop=True)


# ============================================================
# WALL DETECTION
# ============================================================

def detect_positional_call_walls(
    wall_table: pd.DataFrame,
) -> tuple[pd.Series | None, pd.Series | None]:
    """
    Detect highest and second-highest Call OI walls.
    """

    primary = safe_top_row(
        dataframe=wall_table,
        value_column="call_oi",
        rank=1,
    )

    secondary = safe_top_row(
        dataframe=wall_table,
        value_column="call_oi",
        rank=2,
    )

    return primary, secondary


def detect_positional_put_walls(
    wall_table: pd.DataFrame,
) -> tuple[pd.Series | None, pd.Series | None]:
    """
    Detect highest and second-highest Put OI walls.
    """

    primary = safe_top_row(
        dataframe=wall_table,
        value_column="put_oi",
        rank=1,
    )

    secondary = safe_top_row(
        dataframe=wall_table,
        value_column="put_oi",
        rank=2,
    )

    return primary, secondary


def detect_fresh_call_wall(
    wall_table: pd.DataFrame,
) -> pd.Series | None:
    """
    Detect the strike with the highest positive Call Change in OI.
    """

    positive_change = wall_table[
        wall_table["call_change_oi"] > 0
    ].copy()

    return safe_top_row(
        dataframe=positive_change,
        value_column="call_change_oi",
        rank=1,
    )


def detect_fresh_put_wall(
    wall_table: pd.DataFrame,
) -> pd.Series | None:
    """
    Detect the strike with the highest positive Put Change in OI.
    """

    positive_change = wall_table[
        wall_table["put_change_oi"] > 0
    ].copy()

    return safe_top_row(
        dataframe=positive_change,
        value_column="put_change_oi",
        rank=1,
    )


# ============================================================
# WALL SHIFT
# ============================================================

def read_previous_wall(
    history_file: Path,
    column_name: str,
) -> float | None:
    """
    Read the latest available historical wall.
    """

    if not history_file.exists():
        return None

    try:
        history = pd.read_csv(history_file)
    except (
        OSError,
        ValueError,
        pd.errors.ParserError,
    ):
        return None

    if history.empty or column_name not in history.columns:
        return None

    values = pd.to_numeric(
        history[column_name],
        errors="coerce",
    ).dropna()

    if values.empty:
        return None

    return float(values.iloc[-1])


def determine_wall_shift(
    current_wall: float | None,
    previous_wall: float | None,
) -> str:
    """
    Determine whether a wall moved higher, lower or stayed stable.
    """

    if current_wall is None:
        return "NO CURRENT WALL"

    if previous_wall is None:
        return "NO HISTORY"

    if current_wall > previous_wall:
        return "SHIFTED UP"

    if current_wall < previous_wall:
        return "SHIFTED DOWN"

    return "STABLE"


def determine_combined_wall_shift(
    call_wall_shift: str,
    put_wall_shift: str,
) -> str:
    """
    Interpret the combined movement of Call and Put walls.
    """

    if (
        call_wall_shift == "SHIFTED UP"
        and put_wall_shift == "SHIFTED UP"
    ):
        return "RANGE SHIFTED UP"

    if (
        call_wall_shift == "SHIFTED DOWN"
        and put_wall_shift == "SHIFTED DOWN"
    ):
        return "RANGE SHIFTED DOWN"

    if (
        call_wall_shift == "SHIFTED UP"
        and put_wall_shift == "SHIFTED DOWN"
    ):
        return "RANGE EXPANSION"

    if (
        call_wall_shift == "SHIFTED DOWN"
        and put_wall_shift == "SHIFTED UP"
    ):
        return "RANGE COMPRESSION"

    if (
        call_wall_shift == "STABLE"
        and put_wall_shift == "STABLE"
    ):
        return "STABLE RANGE"

    if (
        "NO HISTORY" in {
            call_wall_shift,
            put_wall_shift,
        }
    ):
        return "NO HISTORY"

    return "MIXED WALL SHIFT"


# ============================================================
# RANGE INTELLIGENCE
# ============================================================

def determine_range_bias(
    spot_price: float,
    put_wall: float | None,
    call_wall: float | None,
) -> str:
    """
    Determine where spot is positioned inside the wall range.
    """

    if put_wall is None or call_wall is None:
        return "INSUFFICIENT DATA"

    if call_wall <= put_wall:
        return "OVERLAPPING WALLS"

    range_width = call_wall - put_wall
    location = (
        spot_price - put_wall
    ) / range_width

    if location >= 0.70:
        return "UPPER RANGE — RESISTANCE PRESSURE"

    if location <= 0.30:
        return "LOWER RANGE — SUPPORT ZONE"

    return "MID-RANGE — BALANCED"


def determine_breakout_watch(
    spot_price: float,
    call_wall: float | None,
    strike_step: float,
) -> str:
    """
    Detect proximity to the Call Wall.
    """

    if call_wall is None:
        return "NO CALL WALL"

    tolerance = (
        strike_step
        if strike_step > 0
        else max(spot_price * 0.005, 1.0)
    )

    distance = call_wall - spot_price

    if distance < 0:
        return "SPOT ABOVE CALL WALL — BREAKOUT ACTIVE"

    if distance <= tolerance * 0.50:
        return "VERY CLOSE TO CALL WALL"

    if distance <= tolerance:
        return "CALL WALL TEST APPROACHING"

    return "NO IMMEDIATE BREAKOUT TEST"


def determine_breakdown_watch(
    spot_price: float,
    put_wall: float | None,
    strike_step: float,
) -> str:
    """
    Detect proximity to the Put Wall.
    """

    if put_wall is None:
        return "NO PUT WALL"

    tolerance = (
        strike_step
        if strike_step > 0
        else max(spot_price * 0.005, 1.0)
    )

    distance = spot_price - put_wall

    if distance < 0:
        return "SPOT BELOW PUT WALL — BREAKDOWN ACTIVE"

    if distance <= tolerance * 0.50:
        return "VERY CLOSE TO PUT WALL"

    if distance <= tolerance:
        return "PUT WALL TEST APPROACHING"

    return "NO IMMEDIATE BREAKDOWN TEST"


# ============================================================
# INTERPRETATION
# ============================================================

def build_interpretation(
    result: WallResult,
) -> str:
    """
    Build the Wall Engine interpretation.
    """

    observations: list[str] = []

    if result.positional_put_wall is not None:
        observations.append(
            f"The primary Put Wall is at "
            f"{result.positional_put_wall:,.0f}, "
            f"providing {result.put_wall_strength.lower()} support."
        )

    if result.positional_call_wall is not None:
        observations.append(
            f"The primary Call Wall is at "
            f"{result.positional_call_wall:,.0f}, "
            f"creating {result.call_wall_strength.lower()} resistance."
        )

    if (
        result.expected_range_low is not None
        and result.expected_range_high is not None
    ):
        observations.append(
            f"The current OI-defined range is "
            f"{result.expected_range_low:,.0f} to "
            f"{result.expected_range_high:,.0f}."
        )

    observations.append(
        f"Spot positioning indicates "
        f"{result.range_bias.lower()}."
    )

    if result.fresh_call_wall is not None:
        observations.append(
            f"Fresh Call writing is strongest at "
            f"{result.fresh_call_wall:,.0f}."
        )

    if result.fresh_put_wall is not None:
        observations.append(
            f"Fresh Put writing is strongest at "
            f"{result.fresh_put_wall:,.0f}."
        )

    observations.append(
        f"Combined wall movement is "
        f"{result.combined_wall_shift.lower()}."
    )

    return " ".join(observations)


# ============================================================
# MAIN ENGINE
# ============================================================

def analyze_walls(
    option_chain_data: OptionChainData,
    history_file: Path | None = None,
) -> tuple[WallResult, pd.DataFrame]:
    """
    Run the AQSD Option Wall Engine.
    """

    if history_file is None:
        history_file = (
            OUTPUT_DIR
            / "BANKNIFTY_Wall_History.csv"
        )

    wall_table = build_wall_table(
        option_chain_data
    )

    call_primary, call_secondary = (
        detect_positional_call_walls(
            wall_table
        )
    )

    put_primary, put_secondary = (
        detect_positional_put_walls(
            wall_table
        )
    )

    fresh_call = detect_fresh_call_wall(
        wall_table
    )

    fresh_put = detect_fresh_put_wall(
        wall_table
    )

    positional_call_wall = optional_float(
        call_primary,
        "strike",
    )

    positional_put_wall = optional_float(
        put_primary,
        "strike",
    )

    secondary_call_wall = optional_float(
        call_secondary,
        "strike",
    )

    secondary_put_wall = optional_float(
        put_secondary,
        "strike",
    )

    fresh_call_wall = optional_float(
        fresh_call,
        "strike",
    )

    fresh_put_wall = optional_float(
        fresh_put,
        "strike",
    )

    positional_call_wall_oi = (
        optional_float(
            call_primary,
            "call_oi",
        )
        or 0.0
    )

    positional_put_wall_oi = (
        optional_float(
            put_primary,
            "put_oi",
        )
        or 0.0
    )

    secondary_call_wall_oi = (
        optional_float(
            call_secondary,
            "call_oi",
        )
        or 0.0
    )

    secondary_put_wall_oi = (
        optional_float(
            put_secondary,
            "put_oi",
        )
        or 0.0
    )

    fresh_call_wall_change_oi = (
        optional_float(
            fresh_call,
            "call_change_oi",
        )
        or 0.0
    )

    fresh_put_wall_change_oi = (
        optional_float(
            fresh_put,
            "put_change_oi",
        )
        or 0.0
    )

    call_wall_distance = (
        positional_call_wall
        - option_chain_data.spot_price
        if positional_call_wall is not None
        else None
    )

    put_wall_distance = (
        option_chain_data.spot_price
        - positional_put_wall
        if positional_put_wall is not None
        else None
    )

    call_wall_strength = calculate_wall_strength(
        primary_value=positional_call_wall_oi,
        secondary_value=secondary_call_wall_oi,
    )

    put_wall_strength = calculate_wall_strength(
        primary_value=positional_put_wall_oi,
        secondary_value=secondary_put_wall_oi,
    )

    previous_call_wall = read_previous_wall(
        history_file=history_file,
        column_name="positional_call_wall",
    )

    previous_put_wall = read_previous_wall(
        history_file=history_file,
        column_name="positional_put_wall",
    )

    call_wall_shift = determine_wall_shift(
        current_wall=positional_call_wall,
        previous_wall=previous_call_wall,
    )

    put_wall_shift = determine_wall_shift(
        current_wall=positional_put_wall,
        previous_wall=previous_put_wall,
    )

    combined_wall_shift = (
        determine_combined_wall_shift(
            call_wall_shift=call_wall_shift,
            put_wall_shift=put_wall_shift,
        )
    )

    expected_range_low = positional_put_wall
    expected_range_high = positional_call_wall

    if (
        expected_range_low is not None
        and expected_range_high is not None
    ):
        expected_range_width = (
            expected_range_high
            - expected_range_low
        )
    else:
        expected_range_width = None

    range_bias = determine_range_bias(
        spot_price=option_chain_data.spot_price,
        put_wall=positional_put_wall,
        call_wall=positional_call_wall,
    )

    breakout_watch = determine_breakout_watch(
        spot_price=option_chain_data.spot_price,
        call_wall=positional_call_wall,
        strike_step=option_chain_data.strike_step,
    )

    breakdown_watch = determine_breakdown_watch(
        spot_price=option_chain_data.spot_price,
        put_wall=positional_put_wall,
        strike_step=option_chain_data.strike_step,
    )

    result = WallResult(
        spot_price=option_chain_data.spot_price,
        atm_strike=option_chain_data.atm_strike,
        strike_step=option_chain_data.strike_step,

        positional_call_wall=positional_call_wall,
        positional_call_wall_oi=positional_call_wall_oi,
        secondary_call_wall=secondary_call_wall,
        secondary_call_wall_oi=secondary_call_wall_oi,

        positional_put_wall=positional_put_wall,
        positional_put_wall_oi=positional_put_wall_oi,
        secondary_put_wall=secondary_put_wall,
        secondary_put_wall_oi=secondary_put_wall_oi,

        fresh_call_wall=fresh_call_wall,
        fresh_call_wall_change_oi=(
            fresh_call_wall_change_oi
        ),

        fresh_put_wall=fresh_put_wall,
        fresh_put_wall_change_oi=(
            fresh_put_wall_change_oi
        ),

        call_wall_distance=call_wall_distance,
        put_wall_distance=put_wall_distance,

        call_wall_strength=call_wall_strength,
        put_wall_strength=put_wall_strength,

        expected_range_low=expected_range_low,
        expected_range_high=expected_range_high,
        expected_range_width=expected_range_width,

        call_wall_shift=call_wall_shift,
        put_wall_shift=put_wall_shift,
        combined_wall_shift=combined_wall_shift,

        range_bias=range_bias,
        breakout_watch=breakout_watch,
        breakdown_watch=breakdown_watch,
        interpretation="",

        number_of_strikes=(
            option_chain_data.number_of_strikes
        ),
        timestamp=option_chain_data.timestamp,
    )

    result.interpretation = build_interpretation(
        result
    )

    return result, wall_table


# ============================================================
# OUTPUT FUNCTIONS
# ============================================================

def result_to_dataframe(
    result: WallResult,
) -> pd.DataFrame:
    """
    Convert result into a two-column DataFrame.
    """

    result_dictionary = asdict(result)

    return pd.DataFrame(
        {
            "metric": result_dictionary.keys(),
            "value": result_dictionary.values(),
        }
    )


def append_wall_history(
    result: WallResult,
    history_file: Path,
) -> Path:
    """
    Append the current walls to history.
    """

    history_row = pd.DataFrame(
        [
            {
                "timestamp": result.timestamp,
                "spot_price": result.spot_price,
                "positional_call_wall": (
                    result.positional_call_wall
                ),
                "positional_put_wall": (
                    result.positional_put_wall
                ),
                "fresh_call_wall": (
                    result.fresh_call_wall
                ),
                "fresh_put_wall": (
                    result.fresh_put_wall
                ),
                "call_wall_shift": (
                    result.call_wall_shift
                ),
                "put_wall_shift": (
                    result.put_wall_shift
                ),
                "combined_wall_shift": (
                    result.combined_wall_shift
                ),
            }
        ]
    )

    if history_file.exists():
        history_row.to_csv(
            history_file,
            mode="a",
            header=False,
            index=False,
        )
    else:
        history_row.to_csv(
            history_file,
            index=False,
        )

    return history_file


def save_wall_outputs(
    result: WallResult,
    wall_table: pd.DataFrame,
    prefix: str = "BANKNIFTY",
) -> dict[str, Path]:
    """
    Save wall outputs to CSV and Excel.
    """

    safe_prefix = (
        prefix.strip()
        .upper()
        .replace(" ", "_")
        .replace(":", "_")
    )

    summary_csv = (
        OUTPUT_DIR
        / f"{safe_prefix}_Wall_Summary.csv"
    )

    wall_table_csv = (
        OUTPUT_DIR
        / f"{safe_prefix}_Wall_Table.csv"
    )

    history_csv = (
        OUTPUT_DIR
        / f"{safe_prefix}_Wall_History.csv"
    )

    excel_file = (
        OUTPUT_DIR
        / f"{safe_prefix}_Wall.xlsx"
    )

    summary_dataframe = result_to_dataframe(
        result
    )

    summary_dataframe.to_csv(
        summary_csv,
        index=False,
    )

    wall_table.to_csv(
        wall_table_csv,
        index=False,
    )

    append_wall_history(
        result=result,
        history_file=history_csv,
    )

    history_dataframe = pd.read_csv(
        history_csv
    )

    with pd.ExcelWriter(
        excel_file,
        engine="openpyxl",
    ) as writer:
        summary_dataframe.to_excel(
            writer,
            sheet_name="Wall Summary",
            index=False,
        )

        wall_table.to_excel(
            writer,
            sheet_name="Wall Table",
            index=False,
        )

        history_dataframe.to_excel(
            writer,
            sheet_name="Wall History",
            index=False,
        )

    return {
        "summary_csv": summary_csv,
        "wall_table_csv": wall_table_csv,
        "history_csv": history_csv,
        "excel": excel_file,
    }


# ============================================================
# TERMINAL OUTPUT
# ============================================================

def format_optional_number(
    value: float | None,
) -> str:
    """
    Format optional numeric values.
    """

    if value is None:
        return "N/A"

    return f"{value:,.2f}"


def print_wall_summary(
    result: WallResult,
) -> None:
    """
    Print wall intelligence.
    """

    separator = "=" * 72

    print()
    print(separator)
    print(
        "AQSD OPTION INTELLIGENCE — WALL ENGINE"
    )
    print(separator)

    print(
        f"Spot Price               : "
        f"{result.spot_price:,.2f}"
    )

    print(
        f"ATM Strike               : "
        f"{result.atm_strike:,.2f}"
    )

    print(
        f"Positional Call Wall     : "
        f"{format_optional_number(result.positional_call_wall)}"
    )

    print(
        f"Call Wall OI             : "
        f"{result.positional_call_wall_oi:,.0f}"
    )

    print(
        f"Secondary Call Wall      : "
        f"{format_optional_number(result.secondary_call_wall)}"
    )

    print(
        f"Fresh Call Wall          : "
        f"{format_optional_number(result.fresh_call_wall)}"
    )

    print(
        f"Fresh Call Change OI     : "
        f"{result.fresh_call_wall_change_oi:,.0f}"
    )

    print(
        f"Positional Put Wall      : "
        f"{format_optional_number(result.positional_put_wall)}"
    )

    print(
        f"Put Wall OI              : "
        f"{result.positional_put_wall_oi:,.0f}"
    )

    print(
        f"Secondary Put Wall       : "
        f"{format_optional_number(result.secondary_put_wall)}"
    )

    print(
        f"Fresh Put Wall           : "
        f"{format_optional_number(result.fresh_put_wall)}"
    )

    print(
        f"Fresh Put Change OI      : "
        f"{result.fresh_put_wall_change_oi:,.0f}"
    )

    print(
        f"Expected Range           : "
        f"{format_optional_number(result.expected_range_low)}"
        f" to "
        f"{format_optional_number(result.expected_range_high)}"
    )

    print(
        f"Call Wall Strength       : "
        f"{result.call_wall_strength}"
    )

    print(
        f"Put Wall Strength        : "
        f"{result.put_wall_strength}"
    )

    print(
        f"Call Wall Shift          : "
        f"{result.call_wall_shift}"
    )

    print(
        f"Put Wall Shift           : "
        f"{result.put_wall_shift}"
    )

    print(
        f"Combined Wall Shift      : "
        f"{result.combined_wall_shift}"
    )

    print(
        f"Range Bias               : "
        f"{result.range_bias}"
    )

    print(
        f"Breakout Watch           : "
        f"{result.breakout_watch}"
    )

    print(
        f"Breakdown Watch          : "
        f"{result.breakdown_watch}"
    )

    print()
    print("Interpretation")
    print("-" * 72)
    print(result.interpretation)
    print(separator)
    print()


# ============================================================
# SAMPLE DATA
# ============================================================

def create_sample_option_chain() -> pd.DataFrame:
    """
    Create sample data for independent testing.
    """

    rows: list[dict[str, float | str]] = []

    sample_data = {
        56500: {
            "ce_oi": 90000,
            "pe_oi": 300000,
            "ce_change": 12000,
            "pe_change": 65000,
        },
        57000: {
            "ce_oi": 125000,
            "pe_oi": 410000,
            "ce_change": 18000,
            "pe_change": 72000,
        },
        57500: {
            "ce_oi": 250000,
            "pe_oi": 350000,
            "ce_change": 46000,
            "pe_change": 52000,
        },
        58000: {
            "ce_oi": 520000,
            "pe_oi": 290000,
            "ce_change": 98000,
            "pe_change": 41000,
        },
        58500: {
            "ce_oi": 610000,
            "pe_oi": 185000,
            "ce_change": 122000,
            "pe_change": 18000,
        },
        59000: {
            "ce_oi": 480000,
            "pe_oi": 120000,
            "ce_change": 76000,
            "pe_change": 11000,
        },
    }

    for strike, values in sample_data.items():
        rows.append(
            {
                "strikePrice": strike,
                "optionType": "CE",
                "OI": values["ce_oi"],
                "ChangeOI": values["ce_change"],
                "TotalVolume": 100000,
            }
        )

        rows.append(
            {
                "strikePrice": strike,
                "optionType": "PE",
                "OI": values["pe_oi"],
                "ChangeOI": values["pe_change"],
                "TotalVolume": 100000,
            }
        )

    return pd.DataFrame(rows)

def main() -> None:
    """
    Run an independent sample test using the shared AQSD exporter.
    """

    sample_dataframe = create_sample_option_chain()

    option_chain_data = load_option_chain(
        source=sample_dataframe,
        spot_price=57582.25,
    )

    history_file = (
        OUTPUT_DIR
        / "BANKNIFTY_SAMPLE_Wall_History.csv"
    )

    result, wall_table = analyze_walls(
        option_chain_data=option_chain_data,
        history_file=history_file,
    )

    print_wall_summary(result)

    print("Wall Table")
    print("-" * 72)

    print(
        wall_table[
            [
                "strike",
                "call_oi",
                "put_oi",
                "call_change_oi",
                "put_change_oi",
            ]
        ].to_string(index=False)
    )

    print()

    metadata = ExportMetadata(
        engine="WALL",
        underlying="BANKNIFTY_SAMPLE",
        engine_version="1.0",
        rows_processed=len(sample_dataframe),
        status="SUCCESS",
        source="AQSD Sample Option Chain",
        notes="Independent wall_engine.py module test.",
    )

    history_row = {
        "timestamp": result.timestamp,
        "spot_price": result.spot_price,
        "positional_call_wall": result.positional_call_wall,
        "positional_put_wall": result.positional_put_wall,
        "fresh_call_wall": result.fresh_call_wall,
        "fresh_put_wall": result.fresh_put_wall,
        "call_wall_shift": result.call_wall_shift,
        "put_wall_shift": result.put_wall_shift,
        "combined_wall_shift": result.combined_wall_shift,
    }

    engine_result = EngineResult(
        summary=result,
        table=wall_table,
        history=history_row,
        metadata=metadata,
    )

    export_paths = export_results(
        engine_result=engine_result,
        base_filename="BANKNIFTY_SAMPLE_WALL",
    )

    print_export_report(export_paths)


if __name__ == "__main__":
    main()
"""Automated E2E Scenario Runner for Stella - Size & Fit Advisor.

Executes 10 distinct, highly varied user scenarios against the live Stella engine,
captures multi-turn transcripts, evaluates confidence scores and unit normalizations,
and produces an analytical summary report.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Set UTF-8 encoding for Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from stella.agent import run_consultation, save_session, save_transcript
from stella.config import get_settings
from stella.models import SessionState, UserExpertise

console = Console(force_terminal=True, legacy_windows=False)


@dataclass
class Scenario:
    id: str
    title: str
    expertise: UserExpertise
    answers: list[str]
    description: str


SCENARIOS: list[Scenario] = [
    Scenario(
        id="01_expert_inches",
        title="Expert High-Fashion (Inches)",
        expertise="professional",
        answers=[
            "Bust: 34 inches, Waist: 26 inches, Hips: 36 inches, standard US 4 in designer RTW.",
            "Tailored and structured bodice with clean architectural lines, open to subtle draping.",
            "Black-tie charity gala in November, looking for modern minimalist elegance in silk crepe or heavy satin.",
            "Galvan London bias-cut gown in US 4, fit like a glove because of the high waist apex and flawless bias drape.",
        ],
        description="Tests 100% confidence path, technical styling vocabulary, and structured silhouette matching.",
    ),
    Scenario(
        id="02_novice_mixed_units",
        title="Novice with Mixed Units (cm + m + in)",
        expertise="novice",
        answers=[
            "Bust 88cm, waist 0.72m, hips 37 inches, no brand dress experience.",
            "Something comfortable and flowy that doesn't squeeze my stomach after dinner.",
            "Casual outdoor summer birthday party in warm weather, bright or pastel colors.",
            "A loose cotton sundress from a local market, loved the stretchy smocked back.",
        ],
        description="Tests unit normalizer (cm + m + in), plain-language stylist persona, and relaxed fit advice.",
    ),
    Scenario(
        id="03_vague_probing_retry",
        title="Vague Answers & Probing Retry",
        expertise="novice",
        answers=[
            "I wear medium stuff usually.",  # Triggers retry
            "Around 36 inch bust, 29 waist, 39 hips.",  # Follow-up answer
            "Not too tight, not too baggy.",
            "A wedding.",
            "A dress from Target, don't remember the name.",
        ],
        description="Tests ambiguity handling, follow-up retry mechanism, and low/medium confidence recovery.",
    ),
    Scenario(
        id="04_brand_only_no_tape",
        title="Brand-Only Sizing (No Measuring Tape)",
        expertise="intermediate",
        answers=[
            "I don't have a measuring tape, but I consistently wear a US 8 in Zara dresses and Medium in Aritzia.",
            "Fitted at the waist but flared through the skirt to balance my hips (A-line preferred).",
            "Daytime garden wedding guest, romantic floral or soft sage green aesthetic.",
            "Reformation Kourtney dress in size 8, loved the adjustable straps and smocked back panel.",
        ],
        description="Tests off-the-rack size label extraction, brand reference understanding, and fit heuristics.",
    ),
    Scenario(
        id="05_petite_proportions",
        title="Petite Proportions & Vertical Balance",
        expertise="intermediate",
        answers=[
            "Bust 31 in, Waist 24 in, Hips 33 in. I am 5'1\" so regular maxi dresses always drag on the floor.",
            "Fitted or semi-fitted silhouette that elongates my frame without drowning me in excess fabric.",
            "Cocktail party at an art gallery, chic and modern monochrome.",
            "Petite size 2 sheath dress from Ann Taylor, worked because the torso length was proportional.",
        ],
        description="Tests height/proportion nuance, petite brand tips, and hemline recommendations.",
    ),
    Scenario(
        id="06_curvy_plus_size",
        title="Curvy / Plus Size Proportions",
        expertise="intermediate",
        answers=[
            "Bust 44 inches, Waist 36 inches, Hips 48 inches. Usually wear US 16 or XL.",
            "Empire or wrap style that flatters an hourglass/curvy figure with good bust support.",
            "Evening outdoor winery wedding, sophisticated jewel tone (emerald or sapphire).",
            "City Chic wrap maxi in US 16, loved the deep V-neck and functional tie waist.",
        ],
        description="Tests extended sizing (US 14-18 / XL-2X), bust support styling, and curve-flattering silhouettes.",
    ),
    Scenario(
        id="07_athletic_broad_shoulders",
        title="Athletic Build with Broad Shoulders",
        expertise="professional",
        answers=[
            "Bust 36 in, Waist 29 in, Hips 37 in. Height 5'10\" with wide swimmer shoulders and a straight athletic torso.",
            "Halter or V-neck cuts that soften wide shoulders, with a defined waist to create curves.",
            "Corporate formal awards dinner, bold contemporary styling.",
            "Diane von Furstenberg wrap dress in US 6, collarline drew vertical focus away from shoulder width.",
        ],
        description="Tests anatomical balancing, neckline styling (halters, deep V), and structured tailoring tips.",
    ),
    Scenario(
        id="08_maternity_fluctuating",
        title="Maternity / Fluctuating Waist",
        expertise="novice",
        answers=[
            "Pre-pregnancy bust 34in now 37in, waist 32in fluctuating, hips 38in.",
            "Highly adaptable, forgiving stretch or empire cut with room for a growing belly.",
            "Daytime spring baby shower, soft romantic floral print in breathable fabric.",
            "Smocked bodice midi dress from Hatch in Medium, elastic chest and free waist.",
        ],
        description="Tests adaptive/elastic silhouette suggestions (empire, wrap, smocked) and comfort fabrics.",
    ),
    Scenario(
        id="09_european_metric_pure_cm",
        title="European Metric (Pure Centimeters)",
        expertise="intermediate",
        answers=[
            "Bust 84 cm, waist 66 cm, hips 92 cm. I usually buy French 36 or Italian 40.",
            "Fitted waist with relaxed bias-cut skirt, subtle French effortless look.",
            "Summer holiday dinner in the south of France, romantic linen or silk slip dress.",
            "Rouje wrap dress in size 36, loved the high waist seam and lightweight viscose fabric.",
        ],
        description="Tests pure metric conversion, EU/FR/IT sizing translation, and European brand recommendations.",
    ),
    Scenario(
        id="10_adversarial_off_topic",
        title="Adversarial / Nonsensical Edge Case",
        expertise="novice",
        answers=[
            "I like eating pepperoni pizza with extra cheese.",  # Nonsense -> triggers retry
            "Ok fine, I think my bust is maybe 35 inches and waist 28 inches.",  # Recovery
            "Something like a space astronaut suit.",
            "Dinner on planet Mars.",
            "I never bought clothes in my life.",
        ],
        description="Tests robust error handling, off-topic rejection, anti-hallucination, and safe degradation.",
    ),
]


@dataclass
class ScenarioResult:
    scenario_id: str
    title: str
    expertise: str
    confidence: float
    turns_count: int
    normalized_bust: str
    normalized_waist: str
    normalized_hips: str
    total_tokens: int
    duration_s: float
    transcript_file: str


def run_single_scenario(scenario: Scenario) -> ScenarioResult:
    console.print(f"\n[bold magenta]══════════════════════════════════════════════════════════════[/bold magenta]")
    console.print(f"[bold cyan]▶ Running Scenario {scenario.id}:[/bold cyan] [bold white]{scenario.title}[/bold white]")
    console.print(f"[dim]{scenario.description}[/dim]")
    console.print(f"[bold magenta]══════════════════════════════════════════════════════════════[/bold magenta]\n")

    answers_iter = iter(scenario.answers)

    def scripted_input() -> str:
        try:
            ans = next(answers_iter)
            console.print(f"[bold green]Simulated User >[/bold green] {ans}")
            time.sleep(1.5)
            return ans
        except StopIteration:
            return ""

    state = SessionState(user_expertise=scenario.expertise)
    start_time = time.perf_counter()

    final_state = run_consultation(state=state, input_fn=scripted_input)
    duration = time.perf_counter() - start_time

    # Save dedicated scenario transcript
    transcripts_dir = Path("transcripts")
    transcripts_dir.mkdir(exist_ok=True)
    scenario_transcript_path = transcripts_dir / f"scenario_{scenario.id}_{final_state.session_id}.txt"
    scenario_transcript_path.write_text(final_state.get_transcript(), encoding="utf-8")

    # Read trace log tokens if available
    settings = get_settings()
    trace_file = settings.logs_dir / f"trace_{final_state.session_id}.jsonl"
    total_tokens = 0
    if trace_file.exists():
        for line in trace_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    data = json.loads(line)
                    total_tokens += data.get("total_tokens") or 0
                except Exception:
                    pass

    m = final_state.measurements
    b_str = f"{m.bust_in}in ({m.bust_cm}cm)" if m and m.bust_in is not None else (m.usual_size if m and m.usual_size else "N/A")
    w_str = f"{m.waist_in}in ({m.waist_cm}cm)" if m and m.waist_in is not None else "N/A"
    h_str = f"{m.hips_in}in ({m.hips_cm}cm)" if m and m.hips_in is not None else "N/A"

    return ScenarioResult(
        scenario_id=scenario.id,
        title=scenario.title,
        expertise=scenario.expertise,
        confidence=final_state.confidence,
        turns_count=len(final_state.conversation_history),
        normalized_bust=b_str,
        normalized_waist=w_str,
        normalized_hips=h_str,
        total_tokens=total_tokens,
        duration_s=round(duration, 2),
        transcript_file=str(scenario_transcript_path),
    )


def main() -> None:
    console.print(Panel(
        "[bold magenta]✨ Stella AI Size & Fit Advisor · E2E Scenario Test Suite ✨[/bold magenta]\n"
        "[white]Running 10 end-to-end evaluation personas against live Gemini backend.[/white]",
        border_style="magenta",
        box=box.ROUNDED,
    ))

    results: list[ScenarioResult] = []
    for sc in SCENARIOS:
        try:
            res = run_single_scenario(sc)
            results.append(res)
        except Exception as e:
            console.print(f"[bold red]❌ Scenario {sc.id} failed: {e}[/bold red]")
            results.append(ScenarioResult(
                scenario_id=sc.id,
                title=sc.title,
                expertise=sc.expertise,
                confidence=0.0,
                turns_count=0,
                normalized_bust="ERROR",
                normalized_waist="ERROR",
                normalized_hips="ERROR",
                total_tokens=0,
                duration_s=0.0,
                transcript_file="Failed",
            ))
        time.sleep(2.0)  # Gentle inter-scenario pacing

    # Render Summary Table
    summary_table = Table(
        title="[bold magenta]📊 Stella E2E Evaluation Summary (10 Scenarios)[/bold magenta]",
        box=box.ROUNDED,
        border_style="magenta",
        header_style="bold cyan",
        show_lines=True,
    )

    summary_table.add_column("ID", justify="center", style="bold white")
    summary_table.add_column("Scenario Title")
    summary_table.add_column("Expertise", justify="center")
    summary_table.add_column("Bust (Norm)", justify="center")
    summary_table.add_column("Waist (Norm)", justify="center")
    summary_table.add_column("Hips (Norm)", justify="center")
    summary_table.add_column("Confidence", justify="center")
    summary_table.add_column("Duration (s)", justify="center")
    summary_table.add_column("Total Tokens", justify="center")

    for r in results:
        conf_color = "green" if r.confidence >= 70 else ("yellow" if r.confidence >= 40 else "red")
        summary_table.add_row(
            r.scenario_id,
            r.title,
            r.expertise,
            r.normalized_bust,
            r.normalized_waist,
            r.normalized_hips,
            f"[{conf_color}]{r.confidence:.1f}%[/{conf_color}]",
            f"{r.duration_s}s",
            str(r.total_tokens),
        )

    console.print()
    console.print(summary_table)

    # Save summary report markdown
    report_lines = [
        "# Stella AI - E2E 10-Scenario Evaluation Report",
        "",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| ID | Scenario Title | Expertise | Normalized Bust | Normalized Waist | Normalized Hips | Confidence | Duration | Tokens | Transcript |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        report_lines.append(
            f"| {r.scenario_id} | {r.title} | {r.expertise} | {r.normalized_bust} | {r.normalized_waist} | {r.normalized_hips} | {r.confidence:.1f}% | {r.duration_s}s | {r.total_tokens} | [`{Path(r.transcript_file).name}`]({r.transcript_file}) |"
        )

    report_path = Path("transcripts/E2E_SCENARIO_REPORT.md")
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    console.print(f"\n[green]✓ Complete analytical report saved to:[/green] [bold cyan]{report_path}[/bold cyan]\n")


if __name__ == "__main__":
    main()

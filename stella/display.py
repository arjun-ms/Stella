"""Terminal UI display module for Stella using the Rich library.

Provides styled rendering of welcome banners, dynamic confidence progress bars,
measurement reference guides, stylist messages, recommendations, state dumps,
and user onboarding.
"""

from __future__ import annotations

import sys
from typing import Literal

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from stella.models import UserExpertise

# Ensure UTF-8 output encoding across Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Module-level Console singleton
console: Console = Console(force_terminal=True, legacy_windows=False)


def display_welcome() -> None:
    """Display a warm, styled welcome banner introducing Stella and the consultation process."""
    welcome_text = Text()
    welcome_text.append("✨ Welcome! I'm Stella, your personal dress styling advisor.\n\n", style="bold deep_pink3")
    welcome_text.append(
        "I will guide you through a thoughtful 4-question consultation to determine your ideal dress size, "
        "flattering silhouettes, and personalized brand recommendations:\n\n",
        style="white",
    )
    welcome_text.append("  1. Measurements & Size History (in, cm, or m)\n", style="cyan")
    welcome_text.append("  2. Fit Preferences & Body Silhouette\n", style="cyan")
    welcome_text.append("  3. Style Aesthetic & Event Occasion\n", style="cyan")
    welcome_text.append("  4. Past Purchase Success & What Fit Well\n\n", style="cyan")
    welcome_text.append(
        "Along the way, our styling confidence meter will update in real-time as we learn more about you.",
        style="italic dim",
    )

    panel = Panel(
        welcome_text,
        title="[bold magenta]✨ Stella · AI Dress Styling Advisor ✨[/bold magenta]",
        subtitle="[dim]Personalized Sizing & Silhouette Recommendations[/dim]",
        border_style="deep_pink3",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print()
    console.print(panel)
    console.print()


def get_expertise_choice() -> UserExpertise:
    """Prompt the user to select their fashion/clothing background at onboarding.

    Returns:
        UserExpertise: One of "professional", "novice", or "intermediate".
    """
    menu_text = Text()
    menu_text.append("Before we begin, how would you describe your background with fashion and fit?\n\n", style="white")
    menu_text.append("  [a] Professional / Industry Insider ", style="bold cyan")
    menu_text.append("- I know fashion terminology, cuts, silhouettes, and fabric types.\n", style="dim")
    menu_text.append("  [b] Fashion Novice ", style="bold cyan")
    menu_text.append("- I know little about fashion terms; please keep explanations simple and intuitive.\n", style="dim")
    menu_text.append("  [c] Everyday Shopper ", style="bold cyan")
    menu_text.append("- I know what fits my body in practice, but don't know industry buzzwords.", style="dim")

    panel = Panel(
        menu_text,
        title="[bold magenta]👗 Personalize Your Styling Experience[/bold magenta]",
        border_style="magenta",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)
    console.print()

    mapping: dict[str, UserExpertise] = {
        "a": "professional",
        "b": "novice",
        "c": "intermediate",
        "1": "professional",
        "2": "novice",
        "3": "intermediate",
    }

    while True:
        choice = Prompt.ask(
            "[bold cyan]Select an option[/bold cyan] [magenta](a/b/c)[/magenta]",
            choices=["a", "b", "c", "1", "2", "3"],
            default="c",
        ).strip().lower()

        if choice in mapping:
            selected = mapping[choice]
            labels = {
                "professional": "Professional / Fashion Insider",
                "novice": "Fashion Novice (Simple, plain-language guidance)",
                "intermediate": "Everyday Shopper (Practical fit advice)",
            }
            console.print(f"[green]✓ Profile set to:[/green] [bold magenta]{labels[selected]}[/bold magenta]\n")
            return selected


def display_measurement_guide() -> None:
    """Display a reference table showing how to measure and standard size mappings."""
    guide_table = Table(
        title="[bold magenta]📏 Measurement Guide & Size Reference Chart[/bold magenta]",
        box=box.ROUNDED,
        border_style="magenta",
        header_style="bold cyan",
        show_lines=True,
    )

    guide_table.add_column("Size (Alpha / US)", justify="center", style="bold white")
    guide_table.add_column("Bust", justify="center")
    guide_table.add_column("Waist", justify="center")
    guide_table.add_column("Hips", justify="center")
    guide_table.add_column("How to Measure", style="dim")

    guide_table.add_row(
        "XS (US 0–2)",
        '31–32" (79–82 cm)',
        '24–25" (61–64 cm)',
        '34–35" (86–89 cm)',
        "Measure around the fullest part of your chest with a relaxed breath.",
    )
    guide_table.add_row(
        "S (US 4–6)",
        '33–35" (84–89 cm)',
        '26–28" (66–71 cm)',
        '36–38" (91–97 cm)',
        "Measure around your natural waistline (narrowest part, above navel).",
    )
    guide_table.add_row(
        "M (US 8–10)",
        '36–38" (91–97 cm)',
        '29–31" (74–79 cm)',
        '39–41" (99–104 cm)',
        "Measure around the fullest part of your hips/seat with feet together.",
    )
    guide_table.add_row(
        "L (US 12–14)",
        '39–42" (99–107 cm)',
        '32–35" (81–89 cm)',
        '42–45" (107–114 cm)',
        "Keep the tape snug and parallel to the floor (don't pull too tight).",
    )
    guide_table.add_row(
        "XL (US 16–18)",
        '43–46" (109–117 cm)',
        '36–39" (91–99 cm)',
        '46–49" (117–125 cm)',
        "If you don't have a tape measure, simply share your typical brand size!",
    )

    console.print(guide_table)
    console.print("[dim]💡 Tip: You can provide numbers in [bold cyan]inches (in)[/bold cyan], [bold cyan]centimeters (cm)[/bold cyan], or [bold cyan]meters (m)[/bold cyan]. Stella will normalize them automatically.[/dim]\n")


def display_confidence_bar(confidence: float, step: int) -> None:
    """Render a static confidence progress bar and current step indicator.

    Args:
        confidence: Confidence score as a percentage (0.0 to 100.0).
        step: Current consultation step number (1 to 4).
    """
    clamped_conf = max(0.0, min(100.0, float(confidence)))
    rounded_conf = int(round(clamped_conf))

    # Color coding: red (0-30), yellow (31-60), green (61-100)
    if rounded_conf <= 30:
        color_style = "red"
    elif rounded_conf <= 60:
        color_style = "yellow"
    else:
        color_style = "green"

    bar_width = 20
    filled_blocks = int(round((clamped_conf / 100.0) * bar_width))
    filled_blocks = max(0, min(bar_width, filled_blocks))
    empty_blocks = bar_width - filled_blocks

    bar_text = Text()
    bar_text.append(f"Step {step}/4  •  ", style="bold cyan")
    bar_text.append("Confidence: [", style="dim white")
    bar_text.append("█" * filled_blocks, style=f"bold {color_style}")
    bar_text.append("░" * empty_blocks, style="dim white")
    bar_text.append(f"] {rounded_conf}%", style=f"bold {color_style}")

    panel = Panel(
        bar_text,
        border_style=color_style,
        box=box.ROUNDED,
        padding=(0, 1),
        expand=False,
    )
    console.print(panel)


def display_stella_message(message: str) -> None:
    """Display a response or question from Stella formatted with Markdown.

    Args:
        message: The text or markdown content generated by Stella.
    """
    console.print()
    console.print(Text("✨ Stella:", style="bold deep_pink3"))
    console.print(Markdown(message))
    console.print()


def get_user_input(prompt_text: str = "[bold cyan]You[/bold cyan] > ") -> str:
    """Prompt the user for input with interrupt and EOF handling.

    Args:
        prompt_text: The styled prompt string to display.

    Returns:
        The stripped input string entered by the user, or an empty string on EOF/interrupt.
    """
    try:
        user_input = console.input(prompt_text)
        return user_input.strip()
    except (KeyboardInterrupt, EOFError):
        console.print()
        display_goodbye()
        return ""


def display_recommendation(recommendation: str, confidence: float) -> None:
    """Display the final styling and size recommendation inside a highlighted panel.

    Args:
        recommendation: The markdown recommendation text from Stella.
        confidence: The final confidence score percentage (0.0 to 100.0).
    """
    clamped_conf = max(0.0, min(100.0, float(confidence)))
    rounded_conf = int(round(clamped_conf))

    if rounded_conf <= 30:
        conf_style = "red"
    elif rounded_conf <= 60:
        conf_style = "yellow"
    else:
        conf_style = "green"

    panel = Panel(
        Markdown(recommendation),
        title="[bold magenta]👗 Stella's Tailored Dress Recommendation 👗[/bold magenta]",
        subtitle=f"[{conf_style}]Final Confidence Score: {rounded_conf}%[/{conf_style}]",
        border_style="deep_pink3",
        box=box.DOUBLE,
        padding=(1, 2),
    )
    console.print()
    console.print(panel)
    console.print()


def display_state_dump(dump: str) -> None:
    """Display the current session state dump in a muted inspector panel.

    Args:
        dump: The formatted string dump of the session state.
    """
    panel = Panel(
        Text(dump, style="dim white"),
        title="[dim]🔍 Session State[/dim]",
        border_style="dim",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print()
    console.print(panel)
    console.print()


def display_error(message: str) -> None:
    """Display an error message styled in red.

    Args:
        message: The error description to display.
    """
    panel = Panel(
        Text(f"❌ {message}", style="bold red"),
        title="[bold red]Error[/bold red]",
        border_style="red",
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print()
    console.print(panel)
    console.print()


def display_goodbye() -> None:
    """Display a styled farewell message when the session ends."""
    goodbye_text = Text(
        "Thank you for consulting with Stella. Wishing you impeccable style! ✨",
        style="italic deep_pink3",
    )
    panel = Panel(
        goodbye_text,
        title="[bold magenta]✨ Goodbye ✨[/bold magenta]",
        border_style="magenta",
        box=box.ROUNDED,
        padding=(0, 2),
    )
    console.print()
    console.print(panel)
    console.print()


__all__ = [
    "console",
    "display_confidence_bar",
    "display_error",
    "display_goodbye",
    "display_measurement_guide",
    "display_recommendation",
    "display_state_dump",
    "display_stella_message",
    "display_welcome",
    "get_expertise_choice",
    "get_user_input",
]

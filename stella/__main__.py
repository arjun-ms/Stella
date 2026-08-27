"""CLI entry point for Stella - AI Size & Fit Advisor.

Usage:
    python -m stella              # Start a new consultation
    python -m stella --resume ID  # Resume a saved session
    python -m stella --dump ID    # Print the state dump for a session
"""

from __future__ import annotations

import argparse
import sys

from stella.display import console, display_error, display_state_dump


def main() -> None:
    """Parse CLI arguments and run the appropriate action."""
    parser = argparse.ArgumentParser(
        prog="stella",
        description="Stella - AI Size & Fit Advisor for Women's Dresses",
    )
    parser.add_argument(
        "--resume",
        metavar="SESSION_ID",
        help="Resume a previously saved consultation session by its ID",
    )
    parser.add_argument(
        "--dump",
        metavar="SESSION_ID",
        help="Print the state dump for a saved session without running the consultation",
    )
    parser.add_argument(
        "--export",
        metavar="SESSION_ID",
        help="Export a saved consultation session to a standalone HTML Styling Dossier",
    )
    args = parser.parse_args()

    # Lazy imports so CLI help loads fast even without dependencies
    from stella.agent import load_session, run_consultation

    if args.dump:
        state = load_session(args.dump)
        if state is None:
            display_error(f"No session found with ID: {args.dump}")
            sys.exit(1)
        display_state_dump(state.state_dump())
        return

    if args.export:
        state = load_session(args.export)
        if state is None:
            display_error(f"No session found with ID: {args.export}")
            sys.exit(1)
        from stella.export import export_html_dossier
        export_path = export_html_dossier(state)
        console.print(f"\n[bold green]✓ Standalone HTML Styling Dossier generated:[/bold green] [cyan]{export_path}[/cyan]\n")
        return

    if args.resume:
        state = load_session(args.resume)
        if state is None:
            display_error(f"No session found with ID: {args.resume}")
            sys.exit(1)
        console.print(f"[dim]Resuming session {state.session_id} from step {state.current_step}...[/dim]\n")
        run_consultation(state)
    else:
        run_consultation()


if __name__ == "__main__":
    main()

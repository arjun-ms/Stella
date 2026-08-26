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

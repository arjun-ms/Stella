import os
import json
from pathlib import Path
from stella.export import export_html_dossier
from stella.models import SessionState, ConversationMessage

def test_export_renders_markdown_tables(tmp_path: Path):
    state = SessionState()
    state.session_id = "test1234"
    state.confidence = 90.0
    
    table_markdown = (
        "Here is your table:\n\n"
        "| Size | Bust |\n"
        "| --- | --- |\n"
        "| XS | 32 |\n"
        "| S | 34 |\n"
    )
    
    state.conversation_history = [
        ConversationMessage(role="assistant", content="Recommended Size:\n\n" + table_markdown)
    ]
    
    out_file = export_html_dossier(state, output_dir=tmp_path)
    
    html_content = out_file.read_text(encoding="utf-8")
    assert "<table>" in html_content
    assert "<th>Size</th>" in html_content
    assert "<td>32</td>" in html_content
    assert "<li>" not in html_content  # Should not mistakenly create list items out of nothing

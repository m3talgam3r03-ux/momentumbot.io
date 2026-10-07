"""Guardia sui documenti di progetto: i prompt non devono mai essere troncati per errore.

Il 2026-10-07 si è scoperto che una modifica automatica aveva cancellato il master prompt v1
dopo la tabella delle decisioni: questo test lo avrebbe intercettato subito.
"""

from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
V1_SECTIONS = (
    "<ruolo>", "<missione>", "<identificazione_messaggi>", "<regole_sicurezza>",
    "<filtri_lorenzo>", "<executor>", "<kill_switch>", "<ordine_di_lavoro>", "<consegna_finale>",
)  # fmt: skip
V2_SECTIONS = (
    "<ruolo>", "<missione>", "<decisioni_fisse>", "<formati_reali>", "<regole_sicurezza>",
    "<ordine_di_lavoro>", "<limiti>",
)  # fmt: skip


def test_master_prompt_v1_is_complete() -> None:
    text = (DOCS / "prompt-bot-momentum-fpg.md").read_text(encoding="utf-8")
    for section in V1_SECTIONS:
        assert section in text and section.replace("<", "</") in text, section
    for decision in ("**D1**", "**D2**", "**D3**", "**D4**", "**D5**"):
        assert decision in text, decision


def test_master_prompt_v2_is_complete() -> None:
    text = (DOCS / "MASTER_PROMPT_v2.md").read_text(encoding="utf-8")
    for section in V2_SECTIONS:
        assert section in text and section.replace("<", "</") in text, section
    assert "NEGATIVE_PROMPT.md" not in text

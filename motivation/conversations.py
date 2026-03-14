"""Kempion wisdom dialogues — converse with a piece of wisdom.

"What does Seneca mean by this, given what I'm facing?"
Interprets wisdom through the lens of the seeker's quests, trials,
and inner season. Stays in the poet-warrior-monk voice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from motivation.models import SeekerProfile, WisdomEntry


@dataclass
class DialogueTurn:
    """A single turn in a wisdom dialogue."""

    role: str  # "seeker" | "kempion"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WisdomDialogue:
    """A conversation about a piece of wisdom."""

    wisdom: WisdomEntry
    seeker_id: str
    turns: list[DialogueTurn] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)


class DialogueManager:
    """Manages wisdom dialogues for seekers.

    Note: Actual LLM calls are deferred to Cortex integration.
    This module prepares the context and prompt structure.
    """

    def __init__(self) -> None:
        self._active_dialogues: dict[str, WisdomDialogue] = {}

    def start_dialogue(
        self,
        wisdom: WisdomEntry,
        profile: SeekerProfile,
        initial_question: Optional[str] = None,
    ) -> WisdomDialogue:
        """Start a wisdom dialogue. Returns the dialogue with context prepared."""
        dialogue = WisdomDialogue(wisdom=wisdom, seeker_id=profile.id)

        if initial_question:
            dialogue.turns.append(
                DialogueTurn(role="seeker", content=initial_question)
            )

        dialogue_id = f"{profile.id}:{wisdom.id}"
        self._active_dialogues[dialogue_id] = dialogue
        return dialogue

    def get_dialogue(self, seeker_id: str, wisdom_id: str) -> Optional[WisdomDialogue]:
        return self._active_dialogues.get(f"{seeker_id}:{wisdom_id}")

    def add_seeker_turn(self, seeker_id: str, wisdom_id: str, content: str) -> bool:
        dialogue = self.get_dialogue(seeker_id, wisdom_id)
        if not dialogue:
            return False
        dialogue.turns.append(DialogueTurn(role="seeker", content=content))
        return True

    def add_kempion_response(self, seeker_id: str, wisdom_id: str, content: str) -> bool:
        dialogue = self.get_dialogue(seeker_id, wisdom_id)
        if not dialogue:
            return False
        dialogue.turns.append(DialogueTurn(role="kempion", content=content))
        return True

    def build_dialogue_prompt(
        self,
        wisdom: WisdomEntry,
        profile: SeekerProfile,
        question: str,
    ) -> str:
        """Build the prompt for LLM-powered wisdom interpretation.

        This prompt structure can be sent to Cortex's model router
        for interpretation.
        """
        quest_context = ""
        if profile.active_quests:
            quests = [f"- {q.description} ({q.why})" for q in profile.active_quests[:3]]
            quest_context = "Active quests:\n" + "\n".join(quests)

        trial_context = ""
        if profile.active_trials:
            trials = [
                f"- {t.description} (beneath: {t.truth_beneath})"
                for t in profile.active_trials[:3]
            ]
            trial_context = "Current trials:\n" + "\n".join(trials)

        season_context = f"Inner season: {profile.inner_season.value}"
        values_context = f"Core values: {', '.join(profile.core_values[:5])}"
        aspect_context = f"Dominant aspect: {profile.dominant_aspect}"

        return f"""You are Kempion, a wisdom interpreter for the poet-warrior-monk path.
You speak with the voice of base truth — no toxic positivity, no hustle culture,
no spiritual bypassing. You are part stoic philosopher, part poet, part contemplative.

The seeker asks about this wisdom:

"{wisdom.text}"
— {wisdom.author}{f', {wisdom.source}' if wisdom.source else ''}
Tradition: {wisdom.tradition} | Aspect: {wisdom.aspect.value}

Seeker context:
{season_context}
{aspect_context}
{values_context}
{quest_context}
{trial_context}

The seeker asks: {question}

Respond as Kempion. Be direct, be honest, be wise. Connect the wisdom
to their specific situation. Don't sugarcoat. Don't be verbose.
Speak to the base truth."""

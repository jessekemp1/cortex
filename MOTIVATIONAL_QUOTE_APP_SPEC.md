# Kempion — Wisdom Engine for the Poet-Warrior-Monk

## Vision

A personal wisdom engine built on **base truth** — not motivation porn, not hustle culture, not toxic positivity. Kempion delivers the right truth at the right time, drawn from the deep wells of stoic philosophy, poetic insight, warrior discipline, and contemplative wisdom.

This is a tool for the **poet-warrior-monk**: someone who writes to understand, fights to grow, and sits still to see clearly. It doesn't coddle. It doesn't hype. It finds the signal in the noise and speaks it plainly.

Built on Cortex's persistent intelligence layer — it remembers your path, learns your edges, and sharpens its aim over time.

---

## 1. The Kempion Philosophy

### What "Base Truth" Means
- Strip away comfortable lies, performative optimism, and borrowed conviction
- What remains is base truth: the thing that's actually real about your situation
- Kempion seeks this layer — then finds the wisdom that meets it

### The Three Aspects

**The Poet** — sees clearly, names things precisely, finds beauty in difficulty. Draws from literature, verse, and language that cuts. The poet doesn't decorate — the poet *reveals*.

**The Warrior** — acts despite uncertainty, embraces discipline as freedom, treats obstacles as the path. Draws from stoic endurance, martial philosophy, and the hard-won wisdom of people who built things under pressure.

**The Monk** — sits with discomfort, seeks understanding over reaction, values stillness as a form of strength. Draws from contemplative traditions, meditation philosophy, and the patience of deep practice.

### What Kempion Is NOT
- Not a dopamine hit disguised as wisdom
- Not "you've got this!" when you don't
- Not hustle culture wrapped in a quote card
- Not spiritual bypassing that skips the work
- Not generic — it knows *you*

---

## 2. Wisdom Taxonomy

### 2.1 Source Traditions (weighted by affinity)

| Tradition | Key Voices | Aspect |
|-----------|-----------|--------|
| **Stoicism** | Marcus Aurelius, Seneca, Epictetus, Musonius Rufus | Warrior-Monk |
| **Zen / Chan** | Dogen, Shunryu Suzuki, Thich Nhat Hanh | Monk |
| **Poetry & Literature** | Rumi, Rilke, Mary Oliver, Wendell Berry, Cormac McCarthy, Bukowski | Poet |
| **Martial / Bushido** | Musashi, Hagakure, Sun Tzu | Warrior |
| **Existentialism** | Camus, Kierkegaard, Nietzsche, Frankl | Poet-Warrior |
| **Pragmatism** | Emerson, Thoreau, William James | Monk-Warrior |
| **Modern Depth** | Jordan Peterson (Maps of Meaning era), Nassim Taleb, Jocko Willink, Naval Ravikant, Ryan Holiday | Warrior |
| **Contemplative** | Thomas Merton, Meister Eckhart, The Desert Fathers | Monk |
| **Indigenous Wisdom** | Lakota, Aboriginal, Maori proverbs | Monk-Poet |

### 2.2 Truth Layers

Every piece of wisdom in Kempion is tagged by the layer of truth it addresses:

```python
class TruthLayer(Enum):
    SURFACE = "surface"         # Obvious, immediately actionable
    STRUCTURAL = "structural"   # About systems, habits, patterns
    ROOT = "root"               # About identity, belief, meaning
    PARADOX = "paradox"         # Truths that seem contradictory but aren't
    SILENCE = "silence"         # Beyond words — points at what can't be said
```

### 2.3 The Wisdom Entry

```python
class WisdomEntry:
    text: str
    author: str
    source: str | None          # Book, letter, speech, poem
    tradition: str              # stoic, zen, existentialist, poetic, martial...
    era: str                    # ancient, medieval, modern, contemporary

    # Kempion taxonomy
    aspect: Aspect              # poet | warrior | monk | poet-warrior | warrior-monk | poet-monk | all
    truth_layer: TruthLayer
    themes: list[str]           # discipline, impermanence, courage, solitude, craft...
    domains: list[LifeDomain]
    tone: ToneVector            # severity, warmth, directness

    # Contextual matching
    best_for_seasons: list[InnerSeason]  # forge, desert, summit, consolidation, drift
    challenge_types: list[str]           # self-doubt, discipline, loss, overwhelm, stagnation
    energy_match: str                    # dawn, midday, dusk, dark_night

    # Depth
    requires_context: bool      # True if the quote needs framing to land
    companion_text: str | None  # Optional short framing for depth quotes
    paradox_pair_id: str | None # Links to a quote that holds the opposing truth
```

---

## 3. User Model — The Seeker's Profile

### 3.1 Core Profile

```python
class SeekerProfile:
    # Identity
    name: str
    aspect_balance: dict[Aspect, float]   # poet: 0.4, warrior: 0.35, monk: 0.25
    core_values: list[str]                # truth, craft, endurance, simplicity...
    tradition_affinity: dict[str, float]  # stoicism: 0.8, zen: 0.6, existentialism: 0.5

    # The Path
    quests: list[Quest]                   # Goals reframed as quests
    current_trials: list[Trial]           # Challenges reframed as trials
    inner_season: InnerSeason             # Detected or declared

    # Preferences
    tone_preference: TonePreference       # severe | tempered | gentle
    depth_preference: str                 # surface | structural | root | paradox
    delivery_rhythm: DeliveryRhythm       # dawn, midday, dusk, on_demand

    # Learned
    trigger_words: list[str]              # Words that cut through
    anti_patterns: list[str]              # "toxic positivity", "hustle", "manifest"
    resonance_history: list[str]          # Quote IDs that hit different
```

### 3.2 Inner Seasons (replaces generic "motivational state")

```python
class InnerSeason(Enum):
    FORGE = "forge"             # Active building, grinding, creating under pressure
    DESERT = "desert"           # Dry spell, nothing working, faith tested
    SUMMIT = "summit"           # Peak — things are clicking, breakthroughs happening
    CONSOLIDATION = "consolidation"  # Integrating gains, building foundations
    DRIFT = "drift"             # Lost thread, disconnected from purpose
    DARK_NIGHT = "dark_night"   # Deep crisis, existential weight
```

Each season triggers a different wisdom strategy:
- **Forge** → warrior-dominant. Discipline, endurance, craft. "The obstacle is the way."
- **Desert** → monk-dominant. Patience, faith, emptiness as teacher. "Wait without hope, for hope would be hope of the wrong thing."
- **Summit** → poet-dominant. Gratitude, perspective, impermanence. "This too shall pass — and that's what makes it beautiful."
- **Consolidation** → monk-warrior. Structure, reflection, root-building. "Do not confuse motion with progress."
- **Drift** → poet-warrior. Reconnection, purpose, the call. "What did you come here to do?"
- **Dark Night** → all three at full depth. No platitudes. Raw truth, held gently. "The wound is where the light enters."

### 3.3 Quests and Trials

```python
class Quest:
    description: str            # "Build the product that matters"
    domain: LifeDomain
    why: str                    # The deeper reason — base truth of the quest
    milestones: list[Milestone]
    status: QuestStatus         # walking | stalled | completed | abandoned | questioning

class Trial:
    description: str            # "Discipline is collapsing under pressure"
    severity: float             # 0.0-1.0
    domain: LifeDomain
    truth_beneath: str          # "I'm afraid it won't be good enough"
    related_quest_ids: list[str]
    what_ive_tried: list[str]
```

---

## 4. Wisdom Engine Architecture

### 4.1 Base Truth Scoring

The core algorithm doesn't optimize for "feel good" — it optimizes for **truth that serves growth**:

```
Score(wisdom, seeker, moment) =
    w1 * truth_depth_match(wisdom.truth_layer, seeker.depth_preference)
  + w2 * aspect_alignment(wisdom.aspect, seeker.aspect_balance)
  + w3 * season_fit(wisdom.best_for_seasons, seeker.inner_season)
  + w4 * tradition_affinity(wisdom.tradition, seeker.tradition_affinity)
  + w5 * trial_relevance(wisdom.challenge_types, seeker.current_trials)
  + w6 * quest_alignment(wisdom.domains, seeker.quests)
  + w7 * temporal_resonance(wisdom.energy_match, time_of_day)
  + w8 * novelty(wisdom, seeker.history)
  + w9 * learned_resonance(wisdom, seeker.resonance_history)
  - penalty * repetition_decay(wisdom, seeker.history)
  - penalty * anti_pattern_match(wisdom, seeker.anti_patterns)
```

### 4.2 The Anti-Pattern Guard

Kempion actively filters OUT:
- Toxic positivity ("Everything happens for a reason!" during genuine suffering)
- Hustle porn ("Sleep when you're dead!")
- Spiritual bypassing ("Just let go!" when the work hasn't been done)
- Borrowed conviction (quotes that sound wise but are actually empty)
- Performative depth (pseudo-profound bullshit detector)

### 4.3 Paradox Awareness

Some truths only make sense when held alongside their opposite:
- "Act decisively" AND "Be patient"
- "Let go of outcomes" AND "Fight for what matters"
- "You are enough" AND "You must become more"

Kempion can deliver paradox pairs — two quotes that seem contradictory but together hold a deeper truth.

---

## 5. Key Features

### 5.1 Dawn Briefing
Daily wisdom delivery (default: first thing):
- One piece of wisdom matched to your current season + active trials
- A reflection prompt: "What is the base truth of today?"
- Optional callback: a past quote that proved prophetic

### 5.2 Trial Mode
When you declare a trial (active struggle):
- Curated sequence of 3-5 pieces of wisdom across the day
- Escalates from poet (seeing clearly) → warrior (acting) → monk (accepting)
- End-of-day: "What did the trial teach you today?"

### 5.3 The Commonplace Book
Digital commonplace book — the poet-warrior-monk's journal:
- Annotate wisdom with personal reflections
- Tag entries by quest, trial, or season
- Semantic search: "What wisdom do I have about discipline?"
- Over time, becomes your personal scripture

### 5.4 Wisdom Dialogues
Converse with a piece of wisdom through the lens of your situation:
- "What does Seneca mean when he says this, given what I'm facing?"
- LLM interprets with full context of your profile, quests, trials
- Stays in Kempion voice — no generic chatbot energy

### 5.5 Paradox Pairs
Deliver two apparently contradictory truths together:
- Let the tension between them reveal the deeper insight
- "Hold both of these. The truth is in the space between."

### 5.6 Season Transitions
When Kempion detects a season change:
- Acknowledge the shift
- Deliver transitional wisdom
- "You're leaving the desert. The forge is warming up."

---

## 6. Technical Architecture

### 6.1 Module Structure

```
motivation/
  __init__.py
  models.py              # SeekerProfile, Quest, Trial, WisdomEntry, InnerSeason
  profile_manager.py     # Profile lifecycle, season detection, quest/trial management
  quote_database.py      # Wisdom storage, taxonomy indexing, filtering
  quote_engine.py        # Base-truth scoring, paradox pairing, anti-pattern guard
  delivery.py            # Dawn briefing, trial mode, formatting
  learning.py            # Resonance feedback, anti-pattern learning
  potential.py           # Growth trajectory, domain potential mapping
  conversations.py       # Wisdom dialogues (LLM-powered)
  api.py                 # FastAPI endpoints
  data/
    quotes.json          # Seed wisdom database
```

### 6.2 Cortex Integration

| Cortex Component | Kempion Usage |
|-----------------|---------------|
| `SemanticMemory` | Wisdom embedding index + seeker-context matching |
| `EpisodicMemory` | Past wisdom interactions, what resonated in similar seasons |
| `WorkingMemory` | Current session: active trial, mood, recent events |
| `GoalParser` | Parse natural-language quests into structured `Quest` objects |
| `AntiPatternDB` | Track wisdom types that miss for this seeker |
| `ModelRouter` | Haiku for scoring, Sonnet for wisdom dialogues |
| `Scheduler` | Dawn briefing, trial mode sequences |
| `FeedbackLoop` | Resonance ratings → scoring model improvement |

### 6.3 API Endpoints

```
POST   /api/kempion/profile              # Create/update seeker profile
GET    /api/kempion/profile              # Get current profile
POST   /api/kempion/quests               # Add/update quests
POST   /api/kempion/trials               # Declare a trial
PATCH  /api/kempion/trials/:id/resolve   # Resolve a trial
GET    /api/kempion/wisdom               # Get next wisdom for the seeker
POST   /api/kempion/wisdom/rate          # Rate a wisdom entry (1-5 + "hit different")
GET    /api/kempion/briefing             # Get dawn briefing
POST   /api/kempion/wisdom/dialogue      # Start a wisdom dialogue
GET    /api/kempion/potential             # Get potential map
GET    /api/kempion/trajectory            # Get growth trajectory
POST   /api/kempion/checkin              # Season/state check-in
GET    /api/kempion/commonplace          # Get commonplace book entries
POST   /api/kempion/commonplace          # Add reflection to commonplace book
GET    /api/kempion/paradox              # Get a paradox pair
```

---

## 7. Implementation Phases

### Phase 1 — The Foundation
- [ ] Core models (SeekerProfile, Quest, Trial, WisdomEntry, InnerSeason)
- [ ] Wisdom database with 200+ curated entries from stoic/poetic/martial/contemplative traditions
- [ ] Profile creation and quest/trial management
- [ ] Base-truth scoring algorithm
- [ ] Single wisdom endpoint
- [ ] Basic resonance feedback

### Phase 2 — The Intelligence
- [ ] Cortex memory integration (semantic + episodic)
- [ ] Inner season detection from signals
- [ ] Adaptive scoring with learned resonance weights
- [ ] Dawn briefing generation
- [ ] Trial mode sequences
- [ ] Anti-pattern learning and filtering

### Phase 3 — The Depth
- [ ] Paradox pair system
- [ ] Wisdom dialogues (LLM-powered contextual interpretation)
- [ ] Commonplace book with semantic search
- [ ] Growth trajectory tracking
- [ ] Season transition detection and acknowledgment
- [ ] Cross-domain insight ("your discipline in craft applies to your relationships")

### Phase 4 — The Polish
- [ ] LLM-generated personalized wisdom (in Kempion voice, clearly labeled)
- [ ] Multi-channel: CLI, API, MCP integration
- [ ] Potential mapping visualization
- [ ] Export commonplace book
- [ ] Community wisdom contributions (curated, quality-gated)

---

## 8. Success Metrics

| Metric | Target | Why It Matters |
|--------|--------|---------------|
| "Hit different" rate | >20% | Measures genuine depth penetration |
| Resonance rate (4+ rating) | >50% | Precision of truth-matching |
| Commonplace book entries/week | >3 | Depth of engagement, not just consumption |
| Trial resolution improvement | Decreasing time-to-resolve | Wisdom translating to action |
| Season detection accuracy | >70% agreement with self-report | System understanding the seeker |
| Anti-pattern filter rate | <5% "miss" ratings | Not serving garbage |
| Return after Dark Night | >60% | The hardest test — does it serve in crisis? |

---

## 9. Design Principles — The Kempion Code

1. **Base truth over comfortable lies** — The thing that's actually real, even when it's hard
2. **Precision over volume** — One right truth beats a hundred generic ones
3. **Respect the season** — Don't rush the desert. Don't dampen the forge.
4. **The poet sees, the warrior acts, the monk abides** — All three are needed
5. **Paradox is not contradiction** — Hold opposing truths without collapsing them
6. **Stillness is not passivity** — Sometimes the most powerful thing is to sit with it
7. **Memory deepens wisdom** — The system gets wiser because it remembers your path
8. **No spiritual bypassing** — Don't skip the work. Don't skip the pain.
9. **Agency always** — Wisdom serves action and understanding, never dependency
10. **The wound is the teacher** — What hurts most often has the most to teach

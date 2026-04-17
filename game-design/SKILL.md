---
name: game-design
description: "You MUST consult this skill when reasoning about or evaluating game design decisions — analyzing mechanics, diagnosing why a design feels wrong or shallow, evaluating whether a mechanic is interesting, or discussing game feel, player motivation, balance, or systemic design. Also trigger when a game feels one-note, shallow, or like every other game in its genre. NOT for engine-specific implementation (see godot, love2d) or shader/VFX work (see godot-shader)."
---

# Game Design

Vocabulary and frameworks for reasoning about game design problems — what to build and why.

---

## Core Vocabulary

### Understanding Your Design

**Design / Dynamics / Experience** — From the DDE framework (Walk, Görlich, Barrett 2017). *Design* is what the designer controls: blueprint, rules, interface. *Dynamics* are the runtime behavior that emerges when design elements interact with player input and each other. *Experience* is what the player perceives — sensory, emotional, intellectual. Work at the design layer (write rules, set parameters, define interfaces); evaluate outcomes at the experience layer.

**Depth vs Complexity** — Depth is the meaningful decision space created by interplay between mechanics. Complexity is the raw count of rules, objects, and options. Good design maximizes the ratio of depth to complexity. A game can have 3 mechanics and enormous depth, or 30 mechanics and feel shallow.

**Emergence** — Non-obvious outcomes from combining simple rules. When a system's behavior cannot be predicted by examining individual rules in isolation. The foundation of replayability in systemic games — players discover new combinations rather than exhausting a fixed set of outcomes.

**Interplay / Counterpoint** — How mechanics interact to create depth. Borrowed from music theory: independent voices that follow their own logic but create something richer when combined. A mechanic that doesn't interact with other mechanics contributes complexity without depth. The test: remove the mechanic — does the remaining game lose depth, or just lose content?

### Understanding Your Player

**Player-Subject** — From Sicart (2009). The mental persona that actually plays the game — not the full human, but a subset with different abilities, ethics, and risk tolerance. The Player-Subject can make decisions the real person never would (betray an ally, sacrifice a unit). Designers target the Player-Subject, not the player directly. This distinction matters when designing moral choices, risk systems, and difficulty.

**DKART** — Dexterity, Knowledge, Adaptation, Reflex, Timing. From the Critical Gaming blog (Richard Terrell, archived). The five skill domains a game can test. Analyzing which DKART skills a mechanic exercises reveals whether your game has a rich or narrow skill spectrum. A narrow profile isn't inherently bad — it means the mechanic is focused — but a whole game with one DKART profile may lack variety.

**4 Keys to Fun** — From Nicole Lazzaro (XEODesign). Hard Fun (challenge/mastery), Easy Fun (curiosity/exploration), People Fun (social interaction), Serious Fun (meaning/value). Most successful games serve multiple keys. Useful for diagnosing why a game feels one-note — it's usually serving only one key.

### Evaluating Your Design

**Solvability** — From Sirlin. *Pure solutions* (one best strategy) cause games to degenerate into memorization. *Mixed solutions* (optimal play involves probability distributions) keep games strategically alive. Hidden information, randomness, and real-time execution all push toward mixed solutions. Ask: can a player find a dominant strategy and stop thinking?

**Slippery Slope** — When falling behind makes it harder to catch up, creating a negative feedback loop. The opposite — rubber-banding — can feel artificial. Good designs find middle ground: deficit is meaningful and recoverable, but not self-reinforcing.

**Subtractive Design** — Removing elements to improve the whole. If a mechanic doesn't create interplay with other mechanics, it adds complexity without depth. The discipline of asking "what can I remove?" rather than "what can I add?" A mechanic that survives subtractive scrutiny earns its place.

**Ludo-narrative Coherence** — The embedded narrative (designer-authored story) and the emergent narrative (story arising from dynamics) must harmonize. When they conflict, the player experiences dissonance — the Antagonist (the unified source of challenge: enemy, environment, puzzle, or the player's own limitations) becomes inconsistent. Coined by Clint Hocking (2007); applied here via the DDE framework.

**Game Feel** — How responsive and satisfying moment-to-moment interaction feels. Achieved through feedback layering: animation, sound, camera, particles, hitpause, screenshake. A well-designed mechanic with poor game feel still fails. Distinct from whether the mechanic is strategically interesting — both layers matter independently.

### Building Your Systems

**Permissions / Restrictions / Conditions** — Three rule types for systemic design. *Permissions*: what you can do ("wood burns"). *Restrictions*: exceptions to permissions ("water douses flames"). *Conditions*: the framework for the other two ("most wood is in the forest"). Simple rules in each category combine into complex emergent behavior. The key: keep each rule simple; let combinations do the work.

**Consistency** — Rules must behave the same everywhere. Three aspects: *Predictability* (same inputs → same outputs), *Coherence* (rules work the same in all areas of the game), *Variability* (consistency enables mixing things up because players can reason about outcomes). Inconsistency is the primary source of exploits in systemic games.

**Perceived Affordances** — Can the player intuit what interactions are possible by looking at the game? Spiky things should look dangerous. Flammable things should look flammable. When affordances are clear, players discover rules through play instead of tutorials. When affordances are opaque, players feel cheated by deaths they couldn't predict.

---

## Problem → Concept Routing

| Problem | Concepts | What to Check |
|---|---|---|
| "My game feels shallow/repetitive" | Depth vs Complexity, Interplay | Are mechanics interacting with each other, or existing in isolation? |
| "Players solve it and stop playing" | Solvability | Pure vs mixed solution? Add hidden information, randomness, or real-time execution |
| "Combat/interactions feel flat" | Game Feel, DKART | Is feedback layering adequate? Which skill domains are being tested? |
| "Players keep finding exploits" | Consistency, Permissions/Restrictions | Are rules applied uniformly? Look for inconsistent restrictions |
| "The story feels disconnected from gameplay" | Ludo-narrative Coherence, Player-Subject | Do embedded and emergent narratives harmonize? Is the Antagonist consistent? |
| "My game has too many mechanics" | Subtractive Design, Depth vs Complexity | Which mechanics don't create interplay? Cut them |
| "Players don't understand the systems" | Perceived Affordances, Consistency | Can players discover rules through play? Are affordances clear? |
| "Falling behind feels hopeless" | Slippery Slope | Is there a negative feedback loop? Are comeback mechanics possible without feeling artificial? |
| "The game is fun but I can't explain why" | 4 Keys to Fun, DKART, Emergence | Which keys does it serve? What skills does it test? Where does emergence happen? |
| "My game feels like every other [genre] game" | Interplay, Counterpoint, Subtractive Design | What unique interplay exists? What conventions can you subtract? |
| "Players aren't motivated to continue" | 4 Keys to Fun, Player-Subject | Which emotional needs are unserved? Does the Player-Subject have meaningful agency? |
| "The difficulty feels wrong" | DKART, Slippery Slope | Which skills are overtaxed? Is challenge calibrated to skill growth? |

---

## Worked Examples

### Example 1: Diagnosing a Shallow Design

**Scenario**: "My platformer has 20 enemy types but combat feels repetitive."

Apply **depth vs complexity** and **interplay**. Twenty enemies that all walk toward the player and deal contact damage = high complexity, low depth. The enemies don't interact with each other or with level geometry — they're parallel, not counterpoint.

Depth comes from enemies that create interplay. Spelunky's enemy roster is small but deep — consider three enemy types: one that drops from ceilings, one that patrols the ground, one that flies toward the player with erratic pathfinding. None of these is complex in isolation. But combine them: the ceiling-dropper lands near the ground-patroller, potentially sending it toward the player, who jumps to dodge and triggers an arrow trap. No single enemy caused this — the depth emerged from their interaction.

**Diagnosis**: Don't add more enemy types. Redesign existing enemies so they interact with each other and with level geometry. Three enemies with rich interplay beat twenty that exist in parallel.

---

### Example 2: Evaluating a Mechanic's Skill Profile

**Scenario**: "Is this mechanic interesting enough?"

Apply **DKART** to map the skill profile. Use the BOOST mechanic from Station 38 (Critical Gaming analysis) as a model: click-drag to set direction and power.

- **Dexterity**: High — 360° aim with variable power creates ~17,000 distinct input combinations
- **Knowledge**: Moderate — learn object properties, fuel consumption rates
- **Adaptation**: Moderate — adjust to level geometry and current momentum state
- **Reflex**: Low — static levels, no surprises requiring instant reaction
- **Timing**: High — progressive momentum means approach angle and speed change every maneuver

A narrow DKART profile isn't a flaw — it means the mechanic is focused. But if the whole game shares the same narrow profile, it may lack variety for players who excel in different skill domains. Use DKART to check whether your game's skill demands match your target audience.

---

### Example 3: Checking Rule Consistency

**Scenario**: "Players keep finding exploits in our systemic game."

Apply **consistency** through the **permissions/restrictions/conditions** lens. The most common cause: a material is flammable in one area but not another, or a physics interaction works on some objects but silently fails on others.

Audit process:
1. List all permissions ("wood burns", "enemies can be knocked back", "water conducts electricity")
2. For each permission, verify the restriction and condition boundaries are applied uniformly
3. If "wood burns" is a permission, does ALL wood burn? If not, the exception needs to be a clearly communicated restriction ("wet wood doesn't burn"), not an invisible inconsistency

Invisible inconsistencies feel like exploits to players who discover them and like bugs to players who get burned by them. Explicit restrictions feel like depth — players learn the rule and use it strategically.

---

## Design Analysis Checklist

Run these questions when evaluating a design:

**Depth**: Where does depth come from? Which mechanics create interplay? Could you remove a mechanic without losing depth — and if yes, should you?

**Skill**: What DKART skills does your game test? Is the skill spectrum narrow or broad? Does it match your target audience?

**Motivation**: Which of the 4 Keys does your game serve? Does it serve more than one? Which player needs are unserved?

**Rules**: Are your rules simple, intuitive, and consistent? Can players discover them through play, or do they require tutorials?

**Narrative**: Do embedded and emergent narratives harmonize? Is the game a consistent Antagonist?

**Feel**: Does moment-to-moment interaction feel responsive and satisfying? Is feedback layered appropriately?

---

## References

| File | Contents | Read when... |
|---|---|---|
| `references/frameworks.md` | MDA, DDE, Schell's Tetrad, Costikyan, Lazzaro | You need full framework context or want to analyze a game through multiple lenses |
| `references/depth-and-dynamics.md` | Interplay, counterpoint, complexity vs depth, emergence, DKART deep-dive | You're diagnosing depth problems or analyzing skill spectrums |
| `references/player-experience.md` | 4 Keys to Fun, flow theory, player motivation, game feel, communicating rules | You're evaluating player experience, motivation, difficulty, or game feel |
| `references/systems-and-rules.md` | Systemic design, permissions/restrictions/conditions, state-space decomposition | You're designing rule systems or building a systemic game |
| `references/balance-and-competition.md` | Solvability, slippery slope, subtractive design, economy design | You're tuning balance, competitive design, or resource systems |
| `references/narrative-integration.md` | Ludo-narrative coherence, embedded vs emergent narrative, Player-Subject, Antagonist | You're integrating story with gameplay or diagnosing narrative dissonance |
| `references/design-artifacts.md` | One-page designs, state-space maps, commitment artifacts, game loops | You need to document or communicate design decisions |

---

## Relationship to Other Skills

**game-patterns** — Implementation patterns. game-patterns says "use the State pattern for entity behavioral modes." This skill says "your entity needs distinct behavioral modes" — and explains *why* that's the right design decision. They co-trigger; this skill informs the design choice, game-patterns informs the implementation.

**godot / love2d** — Engine-specific implementation. This skill is engine-agnostic. When both fire, the engine skill handles concrete code; this skill handles design reasoning.

**brainstorm** — Ideation process. This skill provides the domain vocabulary that brainstorm sessions draw on. They co-trigger naturally: brainstorm drives the conversation, game-design provides the concepts to reason with.

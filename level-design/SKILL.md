---
name: level-design
description: "You MUST consult this skill when reasoning about combat arena design, encounter composition, spatial choice in action/shooter levels, player guidance through combat spaces, push-forward layout, or level flow in action games. Also trigger when a level feels like a corridor with decoration, when players camp or disengage, when combat encounters feel static, or when spatial choices feel cosmetic. NOT for puzzle, exploration, or platformer level design. NOT for game mechanics theory or depth analysis (see game-design). NOT for engine-specific implementation (see godot, love2d)."
---

# Level Design

Vocabulary and frameworks for expressing design intent through spatial layout — how to build levels that create meaningful player decisions.

---

## Core Vocabulary

**Spatial Choice** — A decision created by level geometry: which path to take, which threat to address first, which resource to pursue. Spatial choices are meaningful when they are discernible (the player can read the setup) and integrated (the outcome changes the game state). Cosmetic forks that converge immediately are not spatial choices.

**Legibility** — The degree to which a player can read a space before committing to it. Legibility is the prerequisite for choice: a space the player cannot assess forces guessing, not decision-making. Achieved through sightlines, silhouettes, landmarks, and clear geometry.

**Critical Path** — The intended route through a space. Good critical path design makes the intended route the most legible option without eliminating alternatives. The critical path should be discoverable through play, not through a map marker.

**Prioritization Choice** — The highest-value spatial decision: which threat/resource/path to address first, with no obviously dominant answer. Created when enemy compositions, resource placement, and geometry combine into configurations that reward different approaches on different playthroughs. Test with the **Checkpoint Test**: replay the encounter imagining you died — do the patterns rearrange meaningfully?

**Arena Pressure** — The spatial and mechanical forces that push a player toward enemies rather than away from them. Achieved through resource placement (drops come from enemies), geometry (no safe camping positions), and enemy behavior (enemies advance on the player, denying safe positions). The opposite of arena pressure is a space that rewards retreat.

**Push-Forward Design** — A design philosophy where every spatial and mechanical element incentivizes aggressive forward movement. The player restores health by engaging, not abstaining. Geometry rewards movement over camping. Encounters end when the player closes distance, not when they outlast a timer.

**Right-Sized Arena** — An arena scaled so that traversal feels like weaving through traffic, not crossing a field. The player's speed is felt through rapidly passing geometry and direction changes, not raw distance. Arenas that are too large dissipate the feeling of speed and disconnect combat.

**Encounter Composition** — The specific combination of enemy archetypes, spatial geometry, and resource placement that defines a single combat encounter. Enemies are ingredients; the arena and composition are the recipe. A team of all one archetype fails like a basketball team of only centers.

**Last Heavy Standing** — An encounter pacing rule: the encounter ends when the last heavy-class enemy (the **Captain**) dies, not when all AI are cleared. Prevents the anti-climactic straggler-chase and creates a natural climax. See also: Percentage-Based Reinforcements in `references/encounter-design.md`.

**Captain** — The single dominant heavy-class enemy per wave that the Last Heavy Standing check tracks. Each wave should have exactly one captain; multiple captains create confusion about priority and make the encounter feel chaotic rather than challenging.

**Exposed Cover ("Anti-Cover")** — Positioning ranged enemies in open, visible locations rather than behind cover. The design goal is enemies the player can engage, not enemies the player must hunt. Counter-intuitive but essential for push-forward arenas.

**Environmental Behavior** — The illusion of AI having contextual behavior, created through placement rather than AI logic. An imp on an elevated platform appears territorial; a charger in a narrow corridor appears more dangerous. The level designer creates behavior through positioning.

**Asymmetric Layout** — Arena geometry with distinct, non-equivalent navigation options. Asymmetry creates clear landmarks for split-second routing decisions and prevents AI from taking predictable circular routes. Symmetric arenas make options unclear and cause chasing behavior.

---

## Problem → Concept Routing

| Problem | Concepts | What to Check |
|---|---|---|
| Players get lost or don't know where to go | Legibility, Critical Path | Can the player read the space before committing? Is the intended route the most legible option? |
| Players camp in doorways or corners | Arena Pressure, Push-Forward Design | Does the geometry reward staying still? Are resources tied to enemy engagement? |
| Combat encounters feel static or repetitive | Prioritization Choice, Encounter Composition | Does the encounter pass the Checkpoint Test? Are enemy archetypes combined to create non-trivial configurations? |
| Encounters feel too easy or too hard | Right-Sized Arena, Encounter Composition | Is the arena scaled correctly? Is the enemy composition balanced across archetypes? |
| Players snipe from distance and disengage | Arena Pressure, Exposed Cover | Are ranged enemies in exposed positions? Does the arena reward closing distance? |
| Spatial choices feel cosmetic | Spatial Choice, Prioritization Choice | Do the paths have meaningfully different strategic values? Do they interact with enemy behaviors differently? |
| Encounters feel like scripted set pieces | Prioritization Choice, Encounter Composition | Are enemies placed in fixed-script waves? Can the player approach the configuration differently each time? |
| The level feels like a corridor with decoration | Spatial Choice, Legibility | Does the geometry create decisions, or just route the player? Are there meaningful approach vectors? |
| Players don't engage with the most dangerous enemies | Arena Pressure, Encounter Composition | Is there a resource incentive to engage the most dangerous enemies first? Does the Captain drop more health/resources? |
| Encounters lose momentum between waves | Last Heavy Standing, Encounter Composition | Are reinforcements tied to health percentage, not death? Does the encounter have a clear climax? |
| Encounters feel cheap — too many simultaneous attacks | Encounter Composition, Environmental Behavior | How many enemies are actively attacking at once? Use enemy placement and arena geometry to gate simultaneous threats. See token systems in `references/encounter-design.md` |
| AI feels like it has no personality or behavior | Environmental Behavior, Encounter Composition | Are enemies placed to exploit their archetype's strengths? Does placement create the illusion of contextual behavior? |

---

## Worked Examples

### Example 1: Diagnosing a Static Encounter

**Scenario**: "Players run through my combat arenas without engaging — they just sprint to the exit."

Apply **Arena Pressure** and **Push-Forward Design**. If health pickups are static objects scattered around the level, players can ignore enemies and collect them on the way through. If the arena has a clear safe corner, players will find it.

Redesign: tie health drops to enemy kills (glory kills always drop something). Remove static health pickups from the combat space. Size the arena so that the player must pass through enemy positions to reach the exit. Now the fastest path through the space is also the most aggressive path — push-forward design is spatial, not just mechanical.

---

### Example 2: Creating Prioritization Choice

**Scenario**: "My encounters feel like the player just shoots everything in order — there's no interesting decision."

Apply **Prioritization Choice** and **Encounter Composition**. If all enemies are equivalent (same threat level, same behavior class), the player has no basis for prioritization — they shoot the nearest target.

Compose the encounter with orthogonally differentiated archetypes: one hitscan ranged unit (immediate threat, must be addressed), one slow charger (dangerous but telegraphed), one fast flanker (unpredictable positioning). Now the player must decide: address the hitscan unit first (immediate damage prevention) or the flanker (positional threat)? The charger is dangerous but readable. No single script dominates all configurations of this encounter.

Run the **Checkpoint Test**: die and restart. Does the configuration feel different? If no single dominant script emerges — if the player must reassess priorities each time — the encounter has meaningful prioritization choice.

---

### Example 3: Fixing a Too-Large Arena

**Scenario**: "My big boss arena feels slow and disconnected — the combat doesn't feel intense."

Apply **Right-Sized Arena** and **Asymmetric Layout**. A large open circle is the worst arena shape: symmetric (no clear navigation options), too large (player floats rather than weaves), and AI takes circular routes chasing the player.

Redesign: reduce the arena size until traversal feels like weaving through traffic. Add half-walls as line-of-sight breaks that can be jumped over without stopping movement. Make the layout asymmetric — a raised platform on one side, a chokepoint on another, open ground in the center. Now the player has clear binary routing choices (high ground vs. open ground) and the AI has distinct positions that create varied engagement angles.

---

## Design Analysis Checklist

Run these questions when evaluating a combat level or encounter:

**Legibility**: Can the player read the space before committing? Are threats, resources, and paths legible from the entry point?

**Spatial Choice**: Do the paths and positions have meaningfully different strategic values? Do they interact differently with enemy behaviors?

**Prioritization**: Does the encounter pass the Checkpoint Test? Does the configuration feel like a new puzzle on replay, or does one script dominate?

**Arena Pressure**: Does the geometry reward forward movement? Are resources tied to engagement? Is there a safe camping position that needs to be removed?

**Right-Sized Arena**: Is the arena scaled so traversal feels like weaving through traffic? Is the layout asymmetric with clear navigation landmarks?

**Encounter Composition**: Are enemy archetypes combined to create non-trivial configurations? Is there a single Captain per wave? Does the Last Heavy Standing rule apply?

**Environmental Behavior**: Does enemy placement exploit each archetype's strengths? Does placement create the illusion of contextual behavior without complex AI?

**Fail Conditions**: Are players retreating, camping doorways, sniping from distance, or kiting? Any of these signals the space is working against its intent.

---

## References

| File | Contents | Read when... |
|---|---|---|
| `references/spatial-choice.md` | Meaningful choice theory applied to level design, discernibility, the checkpoint test, prioritization choice, autonomy vs. scripting | You're designing encounter layouts, evaluating whether spatial choices are meaningful, or diagnosing scripted-feeling encounters |
| `references/encounter-design.md` | Arena geometry principles, right-sized spaces, asymmetry, half-walls, push-forward resource placement, encounter structure (arena fights vs. wave fights), last heavy standing, token systems | You're building combat arenas, structuring encounter pacing, or placing resources to incentivize aggression |
| `game-design` skill | Mechanic depth, interplay, enemy differentiation theory, orthogonal unit differentiation, DKART skill analysis | You need to evaluate *why* a mechanic or enemy type creates depth — the spatial expression of that depth is this skill's domain |

---

## Relationship to Other Skills

**game-design** — Covers why a mechanic creates depth (interplay, orthogonal differentiation, prioritization choice as a systemic property). This skill covers how to express that depth spatially: arena geometry, encounter composition, resource placement. They co-trigger: game-design explains what makes enemies interesting; this skill explains how to arrange them in space.

**godot / love2d** — Engine-specific implementation. This skill is engine-agnostic. When both fire, the engine skill handles concrete node/object placement; this skill handles the design reasoning behind the layout.

**game-patterns** — Implementation patterns for game systems. This skill informs what spatial configurations to create; game-patterns informs how to implement the systems that make those configurations work.

# Encounter Design and Arena Geometry: Push-Forward Combat in DOOM (2016)

Source: GDC talk by Kurt Louder and Jake Campbell, "Embracing Push Forward Combat in DOOM"

Focus: Spatial and encounter design principles. For combat system depth and enemy differentiation theory, see `game-design`.

---

## Core Thesis

The arena is not a backdrop for combat — it is a participant. The right-sized space with the right geometry makes the player feel fast, in control, and under pressure simultaneously. Arena design, resource placement, and encounter structure are the primary tools for expressing push-forward gameplay spatially.

**Design filter:** Does this space, encounter, or mechanic push the player forward? If it encourages retreat, camping, or disengagement, it works against the design intent.

---

## Arena Design Principles

### 1. Right-Sized Spaces Make Players Feel Fast

The Doom Marine's acceleration and agility exceed top speed — the feeling of speed comes from rapidly passing geometry, changing direction, and weaving between enemies. An arena that is too large dissipates this feeling; the player floats rather than dances.

**Rule of thumb:** Size arenas so that traversal feels like weaving through traffic, not crossing a field. The player should be able to read the entire space and make routing decisions in motion.

**Failure mode:** Epically large arenas do not create epic fights — they create slow, disconnected combat where the player and enemies spend more time closing distance than engaging.

### 2. Asymmetry Over Symmetry

Circular, symmetrical arenas fail for two reasons:
1. Navigation options are unclear — all directions look equivalent
2. AI tends to take the same route, causing the player and enemies to chase each other in circles

Asymmetric layouts create distinct navigation options, clear landmarks for split-second routing decisions, and varied engagement distances. Racing games solve landmarking at 200mph through asymmetry — the same principle applies to combat arenas.

### 3. Half-Walls as the Secret Weapon

Half-walls (waist-height cover) are the ideal arena element for push-forward combat:
- A single jump clears them, maintaining momentum
- A well-timed double jump vaults them cleanly
- They create line-of-sight breaks without stopping movement
- They're impossible to miss — players never get stuck on them

Full walls stop movement and encourage camping. Half-walls redirect movement without interrupting it.

### 4. 360-Degree Combat Requires Open Positioning

Unlike cover shooters where enemies fire from fixed positions, Doom's enemies attack from any direction with the same accuracy on and off screen. This means:
- The arena must protect the player through geometry, not cover
- Enemies need to be able to stand in the open where the player can engage them
- Line-of-sight blockers serve to create routing options, not safe zones

**Anti-cover ("exposed cover"):** Range AI should seek positions where they are visible to the player, not hidden from them. The design goal is enemies the player can engage, not enemies the player must hunt.

### 5. Binary Navigation Choices

Humans make excellent split-second binary decisions but struggle with four or five simultaneous options. Arena layouts should present clear two-option routing choices at decision points — left or right, high or low, through or around.

When too many routes exist simultaneously, players freeze or default to the same path every time. Clarity of options is more important than quantity of options.

---

## Encounter Structure

### Arena Fights vs. Wave Fights

**Wave fights** (traditional): Fixed waves of enemies teleport in sequentially. Problems:
- Feels artificial without environmental context for spawning
- Creates tedium chasing stragglers between waves
- Pacing oscillates severely — intense, then empty, then intense

**Arena fights** (DOOM's backbone): A steady stream of AI reinforcements so the encounter never loses momentum. Key mechanics:
- **Last heavy standing:** Encounter ends when the last heavy-class enemy dies, not when all AI are dead. This prevents the anti-climactic straggler-chase.
- **Percentage-based reinforcements:** New AI spawn when existing AI drop to ~50% health, not on death. Reinforcements feel less contrived and limit cheap potshots.
- **Zerg rush on last heavy death:** Remaining fodder rush the player immediately after the last heavy dies, cleaning up the encounter quickly.

Target: 5 minutes, 3 waves for big encounters.

### The "Last Heavy Standing" Rule

Encounters hinge around heavy-class enemies. Checking whether a heavy is still alive (rather than counting all AI) creates:
- A clear climax to each encounter
- Incentive for players to target the most dangerous enemies first
- Natural pacing without artificial wave breaks

### Incentivizing Aggression Through Resource Placement

Resources (health, ammo) drop from enemies, not from static pickups. This creates a direct spatial incentive: to get resources, the player must move toward enemies and engage them. Standing back and sniping starves the player of resources.

Key resource design decisions:
- **Health rubber-bands:** Drops scale with enemy difficulty — harder enemies drop more health, incentivizing players to tackle the most dangerous foes when in dire straits
- **Ammo does not rubber-band:** Tools are useless if the player can use the same one the entire game. Ammo scarcity forces weapon switching.
- **Glory kills always drop something:** Even when topped off, glory kills produce drops. This removes the calculation "should I glory kill?" — the answer is always yes if the player wants resources.
- **Chainsaw as ammo pinata:** The chainsaw consumes rare fuel but instantly refills a weapon's ammo. Fuel scarcity forces players to choose targets strategically — fodder is fuel-efficient, but a heavy is tempting.

### Active Attacker Count

The fantasy is overwhelming odds; the reality is carefully managed pressure. Limiting the number of enemies that can attack simultaneously:
- Prevents the player from feeling cheated by simultaneous volleys
- Maintains the illusion of overwhelming numbers while keeping combat readable
- Scales with difficulty: more simultaneous attackers on harder settings

**Token system:** Enemies request attack tokens before executing certain attacks. If no token is available, they reposition or taunt instead. This creates natural rhythm and predictability in enemy attack patterns.

---

## Enemy Placement as Spatial Design

### Ingredients, Not Entrées

Enemies are chess pieces designed to facilitate specific player responses. They are not self-contained encounters — they are ingredients whose combination creates the encounter. A team composed entirely of one archetype (all chargers, all ranged) fails like a basketball team of only centers.

**One captain per wave:** Encounters should have a single dominant threat (the "captain") that the last-heavy-standing check tracks. Multiple dominant threats create confusion about priority and make the encounter feel chaotic rather than challenging.

### Environment as Behavior Modifier

Clever AI placement can create the illusion of built-in environmental behavior. An imp in a hangout position (elevated, overlooking the arena) appears to have territorial behavior — but it's the placement, not the AI, doing the work. The level designer creates the behavior through positioning.

**Phat Guiana principle:** An incubus in a hallway appears more formidable than the same enemy in an open arena. The player's reduced movement options change the encounter's difficulty without changing the AI at all. Spatial constraints are a difficulty dial.

### Encounter Fail Conditions

An encounter is failing if players exhibit these behaviors:
- Retreating from enemies (space is too dangerous to advance)
- Posting up in a doorway (geometry rewards camping)
- Sniping from distance (arena is too large or enemies don't pressure)
- Kiting enemies around the space (no incentive to engage)

These behaviors indicate the arena geometry or encounter composition is working against push-forward intent.

---

## Anti-Patterns

**Epically sized arenas:** Counter-intuitively, large arenas make combat feel slower and less intense. The player and enemies spend time crossing distance rather than engaging.

**Symmetrical layouts:** Circular or symmetric arenas make navigation options unclear and cause AI to take predictable routes.

**Full-wall cover:** Encourages camping and disengagement. Half-walls maintain momentum while providing routing options.

**Fixed-position ranged AI:** Enemies that hide from the player create a hunting game, not a combat game. Ranged AI should seek exposed positions where the player can engage them.

**Simultaneous melee chargers:** Two or more charging melee units attacking simultaneously overwhelm the player's ability to respond. Like moving two chess pieces at once — it breaks the game's strategic logic.

**Wave fights without environmental context:** Enemies teleporting in without a portal, alarm, or other spatial justification breaks immersion and makes the encounter feel arbitrary.

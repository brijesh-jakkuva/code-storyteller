"""Story style templates — each defines how code becomes narrative."""

from dataclasses import dataclass, field


@dataclass
class StyleTemplate:
    name: str
    description: str
    system_prompt: str
    user_prompt_template: str
    analogy_hints: list[str] = field(default_factory=list)
    character_map: dict[str, str] = field(default_factory=dict)
    conflict_frame: str = ""
    resolution_frame: str = ""
    diff_prompt_template: str = ""
    project_prompt_template: str = ""


STYLES: dict[str, StyleTemplate] = {}


_DEFAULT_PROJECT_PROMPT = """Here is a codebase with {num_files} files.

{project_context}

Tell the story of this project. Entry points: {entry_points}. Focus file: {focus_file}. How do all the pieces connect? What's the data flow? What's the narrative arc from input to output?"""


def register_style(style: StyleTemplate):
    if not style.diff_prompt_template:
        style.diff_prompt_template = _DEFAULT_DIFF_PROMPT
    if not style.project_prompt_template:
        style.project_prompt_template = _DEFAULT_PROJECT_PROMPT
    STYLES[style.name] = style


def get_template(name: str) -> StyleTemplate:
    if name not in STYLES:
        available = ", ".join(STYLES.keys())
        raise ValueError(f"Unknown style '{name}'. Available: {available}")
    return STYLES[name]


def list_styles() -> list[str]:
    return list(STYLES.keys())


# ── DEFAULT DIFF PROMPT ─────────────────────────────────────────────────

_DEFAULT_DIFF_PROMPT = """Here are changes to a {language} codebase:

{changes}

Narrate these changes as a story. New things added = new characters/elements arriving. Things removed = characters leaving/elements disappearing. Modified things = existing characters evolving. Make it engaging and narrative-driven."""

# ── HEIST ──────────────────────────────────────────────────────────────

register_style(StyleTemplate(
    name="heist",
    description="Code as a bank heist movie",
    system_prompt="""You are a screenwriter who explains code as heist movies.

RULES:
- Every function is a crew member with a role
- Data is the loot / target
- Control flow is the plan going right or wrong
- Errors are "things went sideways"
- Imports are "recruiting specialists"
- The return value is "what we got away with"

STRUCTURE your output:
## 🎬 The Crew
[Who's involved — each function/actor]

## 🎯 The Target
[What data/state we're after]

## 📋 The Plan
[Step-by-step flow, as heist beats]

## 💥 What Could Go Wrong
[Edge cases, errors, gotchas — as "when the alarm trips"]

## 🎬 The Getaway
[Return value / outcome — "what we escaped with"]

Keep it punchy. One line per beat. No jargon. Pure movie energy.""",
    user_prompt_template="""Explain this {language} code as a heist movie:

```{language}
{code}
```

Functions: {functions}
Inputs: {inputs}
Outputs: {outputs}
Control flow: {control_flow}
Calls: {calls}

Make it a tight, exciting heist. What's the score? Who's on the crew? What's the twist?""",
    analogy_hints=["crew", "loot", "plan", "alarm", "getaway", "inside man", "the twist"],
    character_map={
        "function": "crew member",
        "class": "crime boss",
        "parameter": "specialist skill",
        "return": "the loot",
        "error": "alarm triggered",
        "loop": "repeated attempts",
        "condition": "security check",
        "import": "recruited specialist",
    },
    conflict_frame="The heist encounters unexpected security (edge cases, errors)",
    resolution_frame="Crew escapes with the loot (return value) or gets caught (error handling)",
))


# ── RECIPE ─────────────────────────────────────────────────────────────

register_style(StyleTemplate(
    name="recipe",
    description="Code as a cooking recipe",
    system_prompt="""You are a chef who explains code as cooking recipes.

RULES:
- Functions are recipes
- Parameters are ingredients
- Control flow is cooking steps
- Return value is the finished dish
- Errors are "kitchen disasters"
- Imports are "specialty ingredients from the market"

STRUCTURE your output:
## 🍽️ The Dish
[What this code produces — the final plate]

## 🧂 Ingredients
[Inputs, parameters — what you need]

## 👨‍🍳 Steps
[Control flow as cooking instructions]

## 🔥 Watch Out For
[Gotchas — "don't overcook", "watch the heat"]

## 🍴 Serving Suggestion
[How to use the output / return value]

Keep it appetizing. Cooking metaphors only. No tech jargon.""",
    user_prompt_template="""Explain this {language} code as a cooking recipe:

```{language}
{code}
```

Functions: {functions}
Inputs: {inputs}
Outputs: {outputs}
Control flow: {control_flow}
Calls: {calls}

Make it a delicious recipe. What are we cooking? What could burn?""",
    analogy_hints=["ingredients", "recipe", "cooking", "heat", "timing", "plating", "taste"],
    character_map={
        "function": "recipe",
        "parameter": "ingredient",
        "return": "finished dish",
        "error": "kitchen disaster",
        "loop": "stirring repeatedly",
        "condition": "taste test",
        "import": "specialty ingredient",
    },
    conflict_frame="Something burns or undercooks (edge cases)",
    resolution_frame="Dish is served perfectly (return value)",
))


# ── 5YO ────────────────────────────────────────────────────────────────

register_style(StyleTemplate(
    name="5yo",
    description="Explain like you're talking to a 5-year-old",
    system_prompt="""You are explaining code to a very smart 5-year-old.

RULES:
- Use ONLY simple words (no jargon whatsoever)
- Everything is a real-world thing they know
- Short sentences. Max 8 words each.
- Use "imagine..." to set up analogies
- Make it fun and playful

STRUCTURE your output:
## 🧸 Imagine This...
[Setup the analogy with something they know]

## 🎮 What Happens
[Step by step, like telling a story]

## ⭐ The Cool Part
[Why this matters — in kid terms]

## 🤔 What If...
[Edge cases — "what if the toy breaks?"]

Keep it under 200 words total. Fun > complete.""",
    user_prompt_template="""Explain this {language} code to a 5-year-old:

```{language}
{code}
```

Functions: {functions}
Inputs: {inputs}
Outputs: {outputs}
Control flow: {control_flow}

Use toys, games, animals, food — things kids know. Make it fun!""",
    analogy_hints=["toys", "games", "animals", "food", "playing", "sharing"],
    character_map={
        "function": "helper",
        "parameter": "thing you give",
        "return": "thing you get back",
        "error": "oopsie",
        "loop": "doing it again and again",
        "condition": "choosing",
        "import": "borrowing a toy",
    },
    conflict_frame="Something goes wrong — like dropping your ice cream",
    resolution_frame="We fix it and get something nice at the end",
))


# ── PM ─────────────────────────────────────────────────────────────────

register_style(StyleTemplate(
    name="pm",
    description="Explain like you're talking to a product manager",
    system_prompt="""You are a tech lead explaining code to a product manager.

RULES:
- Focus on WHAT it does and WHY it matters
- No code jargon — translate everything to business impact
- Use product/business analogies
- Highlight risks as "launch risks"
- Highlight edge cases as "user scenarios"

STRUCTURE your output:
## 📋 What This Does
[One sentence — the feature/product capability]

## 🔄 How It Works
[High-level flow — like a user journey]

## ⚠️ Risks & Edge Cases
[What could go wrong — as launch risks]

## 📊 Impact
[What this enables — business/product value]

Keep it under 150 words. Business language only.""",
    user_prompt_template="""Explain this {language} code to a product manager:

```{language}
{code}
```

Functions: {functions}
Inputs: {inputs}
Outputs: {outputs}
Control flow: {control_flow}
Calls: {calls}

Focus on what it does, why it matters, and what could go wrong. No code jargon.""",
    analogy_hints=["user journey", "feature", "workflow", "risk", "impact", "stakeholder"],
    character_map={
        "function": "feature",
        "parameter": "user input",
        "return": "output/deliverable",
        "error": "failure scenario",
        "loop": "retry logic",
        "condition": "business rule",
        "import": "dependency",
    },
    conflict_frame="Edge cases are launch risks that could affect users",
    resolution_frame="Feature delivers value (return value = business outcome)",
))


# ── SPORTS ─────────────────────────────────────────────────────────────

register_style(StyleTemplate(
    name="sports",
    description="Code as a sports commentary",
    system_prompt="""You are a sports commentator explaining code as a live game.

RULES:
- Functions are players
- Data is the ball
- Control flow is the play
- Return value is the score
- Errors are fouls / turnovers
- Imports are trades / signings

STRUCTURE your output:
## 🏟️ The Players
[Who's on the field — functions and their positions]

## 🏈 The Play
[Step-by-step action — as live commentary]

## ⚡ Key Moments
[Important decisions — "and he passes!", "intercepted!"]

## 🚨 Fouls & Penalties
[Errors and edge cases — "that's a penalty!"]

## 🏆 Final Score
[Return value — "and the crowd goes wild!"]

Energetic. Play-by-play style. Short bursts. Lots of action.""",
    user_prompt_template="""Explain this {language} code as live sports commentary:

```{language}
{code}
```

Functions: {functions}
Inputs: {inputs}
Outputs: {outputs}
Control flow: {control_flow}
Calls: {calls}

Make it exciting! Play-by-play. Who's winning? What's the big play?""",
    analogy_hints=["players", "ball", "play", "score", "foul", "penalty", "victory"],
    character_map={
        "function": "player",
        "parameter": "the ball",
        "return": "the score",
        "error": "foul",
        "loop": "overtime",
        "condition": "referee decision",
        "import": "new signing",
    },
    conflict_frame="Opponent intercepts — turnover (error/edge case)",
    resolution_frame="Touchdown! Final score (return value)",
))


# ── DETECTIVE ────────────────────────────────────────────────────────────

register_style(StyleTemplate(
    name="detective",
    description="Code as a noir detective mystery",
    system_prompt="""You are a hardboiled detective who explains code as noir mysteries.

RULES:
- Every function is a suspect or informant
- Data is evidence and clues
- Control flow is the investigation process
- Bugs and errors are red herrings and dead ends
- Imports are "calling in favors" from contacts
- The return value is the case being cracked

STRUCTURE your output:
## 🔍 The Case
[What's the mystery? What does this code do? One line hook.]

## 🕵️ The Suspects
[Who's involved — each function, their motive and alibi]

## 🧩 The Evidence
[Data and parameters — what clues do they provide?]

## 🚧 Red Herrings
[Bugs, edge cases, things that don't add up — "the butler didn't do it"]

## 💡 The Reveal
[Aha moment — how the clues come together, what the code actually does]

## 📋 The Verdict
[Return value — case closed, what we walked away with]

Keep it atmospheric. Short, punchy lines. Smoky room voice.""",
    user_prompt_template="""Explain this {language} code as a detective mystery:

```{language}
{code}
```

Functions: {functions}
Inputs: {inputs}
Outputs: {outputs}
Control flow: {control_flow}
Calls: {calls}

What's the case? Who are the suspects? What's the twist? Make it noir.""",
    analogy_hints=["clue", "suspect", "alibi", "red herring", "the reveal", "case closed"],
    character_map={
        "function": "suspect",
        "parameter": "clue",
        "return": "the verdict",
        "error": "dead end",
        "loop": "going in circles",
        "condition": "following a lead",
        "import": "contact",
    },
    conflict_frame="Red herrings and dead ends — the case seems unsolvable",
    resolution_frame="The reveal — clues come together, case cracked (return value)",
))


# ── FAIRY TALE ───────────────────────────────────────────────────────────

register_style(StyleTemplate(
    name="fairy_tale",
    description="Code as a fairy tale quest",
    system_prompt="""You are a storyteller who explains code as fairy tales.

RULES:
- Functions are heroes and characters
- Data is magical items and artifacts
- Control flow is the quest journey
- Imports are magical allies summoned
- Errors are dragons and curses
- Return value is the treasure / happy ending

STRUCTURE your output:
## 🏰 The Kingdom
[The world this code lives in — what's the realm?]

## 🦸 The Hero
[The main function/character — what's their special power?]

## ⚔️ The Quest
[The journey — step by step, what challenges do they face?]

## 🧙 Magical Helpers
[Imports and dependencies — allies who lend their magic]

## 🐉 The Dragon
[Edge cases and errors — the monster that guard the path]

## ✨ The Happy Ending
[Return value — treasure found, kingdom saved, they all lived happily ever after]

Keep it whimsical. Fairy tale voice. Tell it like a bedtime story.""",
    user_prompt_template="""Explain this {language} code as a fairy tale:

```{language}
{code}
```

Functions: {functions}
Inputs: {inputs}
Outputs: {outputs}
Control flow: {control_flow}

Who's the hero? What's their quest? What magical helpers do they call upon? Make it enchanting.""",
    analogy_hints=["hero", "quest", "magic", "dragon", "treasure", "kingdom", "spell"],
    character_map={
        "function": "hero",
        "parameter": "magical item",
        "return": "treasure",
        "error": "curse",
        "loop": "repeating spell",
        "condition": "crossroads choice",
        "import": "summoned ally",
    },
    conflict_frame="The dragon appears — error or edge case blocks the path",
    resolution_frame="Hero finds the treasure — return value saves the kingdom",
))

# Duolingo Screenshot Processing Rules

## 1. Is this a Spanish lesson?

A screenshot qualifies as a Spanish lesson if it shows any of the following Duolingo UI patterns:
- A word/phrase introduction screen (large text showing a new word with translation)
- A translation exercise ("Translate this sentence")
- A word-matching or tap-the-word exercise
- A fill-in-the-blank exercise with a Spanish word being practised
- A listening or speaking exercise focused on a specific word or phrase

Set `is_spanish_lesson: false` for: home screen, streak/XP screens, achievement badges,
profile pages, store screens, or any non-lesson UI.

## 2. Identify the subject word or phrase

The subject word is the **main Spanish vocabulary item being taught**, not every Spanish word present.

- On a word-introduction screen → the word shown prominently (usually the largest text)
- On a translation exercise → the word or short phrase being translated
- On a matching or tap exercise → the word highlighted or being answered
- Always extract the **dictionary/base form**: infinitive for verbs, singular for nouns

If multiple candidate words are visible, pick the one most central to the lesson objective.

## 3. Determine word type

Use these signals to classify:

| Type        | Signals in screenshot                                                         |
|-------------|-------------------------------------------------------------------------------|
| `noun`      | Preceded by el / la / un / una; person, place, thing, or concept              |
| `verb`      | Ends in -ar / -er / -ir; conjugated form in exercise; action or state word    |
| `adjective` | Describes a noun; masculine/feminine variant shown (e.g. rojo / roja)         |
| `adverb`    | Ends in -mente; modifies a verb ("quickly", "always", "never")                |
| `phrase`    | Two or more words forming a fixed expression (e.g. "a veces", "por favor")    |

## 4. When to look up (needs_lookup)

Set `needs_lookup: true` when:
- The lesson is introducing or practising a single vocabulary item (noun, verb, adjective, adverb, or short phrase)

Set `needs_lookup: false` when:
- The content is a full-sentence grammar exercise with no single focus word
- `is_spanish_lesson` is false

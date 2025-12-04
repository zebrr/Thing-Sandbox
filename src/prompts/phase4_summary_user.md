# Phase 4: Summary — User Prompt

## Character

**{{ character.identity.name }}**

{{ character.identity.description }}

## Old Summary

{{ character.memory.summary | default("Nothing yet — this is the beginning of your story.") }}

## Dropping Memory

{{ character.memory.cells[-1].text if character.memory.cells else "No memory to drop." }}

## Tick

{{ simulation.current_tick }}

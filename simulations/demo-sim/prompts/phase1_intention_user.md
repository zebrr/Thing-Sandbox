# Phase 1: Intention — User Prompt

## Character

**Your name:** {{ character.identity.name }}

{{ character.identity.description }}

**Your habits:** {{ character.identity.triggers | default("You have no specific behavior patterns.") }}

## Your State

**How you feel:** {{ character.state.internal_state | default("You feel normal, nothing special.") }}

**What you want:** {{ character.state.external_intent | default("No particular goal right now.") }}

## Your Memories (newest first)

**Recent:**
{% if character.memory.cells %}
{% for cell in character.memory.cells -%}
- {{ cell.text }}
{% endfor %}
{% else %}
Nothing has happened yet.
{% endif %}

**Long ago:** {{ character.memory.summary | default("You don't remember anything from long ago.") }}

## Location

**{{ location.identity.name }}:** {{ location.identity.description }}

**Right now:** {{ location.state.moment }}

**You can go:**
{% for conn in location.identity.connections -%}
- {{ conn.description }} → {{ conn.location_id }}
{% endfor %}

## Present Here

{% if others %}
{% for other in others -%}
- **{{ other.identity.name }}:** {{ other.identity.description }}
{% endfor %}
{% else %}
You are alone here.
{% endif %}

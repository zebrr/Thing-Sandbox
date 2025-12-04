# Phase 2a: Resolution — User Prompt

## Location

**{{ location.identity.name }}** ({{ location.identity.id }})

{{ location.identity.description }}

**Right now:** {{ location.state.moment }}

**Connections:**
{% for conn in location.identity.connections -%}
- {{ conn.description }} → {{ conn.location_id }}
{% endfor %}

## Characters

{% if characters %}
{% for char in characters %}
### {{ char.identity.name }} ({{ char.identity.id }})

{{ char.identity.description }}

**Triggers:** {{ char.identity.triggers | default("No specific triggers.") }}

**Internal state:** {{ char.state.internal_state | default("Unknown.") }}

**Current focus:** {{ char.state.external_intent | default("Unknown.") }}

{% endfor %}
{% else %}
No characters present.
{% endif %}

## Intentions

{% if intentions %}
{% for char_id, intention in intentions.items() %}
**{{ char_id }}:** {{ intention }}

{% endfor %}
{% else %}
No intentions — empty location.
{% endif %}

## Tick

{{ simulation.current_tick }}

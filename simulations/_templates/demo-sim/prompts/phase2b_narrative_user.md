# Phase 2b: Narrative — User Prompt

## Location

**{{ location_before.identity.name }}**

{{ location_before.identity.description }}

**Before:** {{ location_before.state.moment }}

**After Game Master's resolution:** {{ master_result.location.moment | default(location_before.state.moment) }}

{% if master_result.location.description %}
**Changed to:** {{ master_result.location.description }}
{% endif %}

## Characters

{% if characters_before %}
{% for char in characters_before %}
### {{ char.identity.name }}

{{ char.identity.description }}

**Triggers:** {{ char.identity.triggers | default("No specific behavior patterns.") }}

**Before:** {{ char.state.internal_state | default("Unknown") }} / {{ char.state.external_intent | default("Unknown") }}

**Intended:** {{ intentions[char.identity.id] | default("No intention.") }}

{% set result = master_result.characters[char.identity.id] %}
{% if result %}
**After Game Master's resolution:** {{ result.internal_state }} / {{ result.external_intent }}
{% if result.location != char.state.location %}
{% for conn in location_before.identity.connections %}
{% if conn.location_id == result.location %}
**Moving to:** {{ conn.description }}
{% endif %}
{% endfor %}
{% endif %}
{% endif %}

{% endfor %}
{% else %}
No characters — just the world living on.
{% endif %}

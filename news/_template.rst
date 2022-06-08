{% macro reference(value) -%}
   {%- if value.startswith("PR") -%}
     :pr:`{{ value[2:] }}`
   {%- elif value.startswith("C") -%}
     :commit:`{{ value[1:] }}`
   {%- else -%}
     :issue:`{{ value }}`
   {%- endif -%}
{%- endmacro -%}


{{ top_line }}
{{ top_underline * ((top_line)|length)}}

Released on {{ versiondata.date }}.
This is a {major|feature|bugfix} release that adds [short summary].

{% for section, _ in sections.items() %}
{% set underline = underlines[0] %}{% if section %}{{section}}
{{ underline * section|length }}{% set underline = underlines[1] %}

{% endif %}

{% if sections[section] %}
{% for category, val in definitions.items() if category in sections[section] and category != "author" %}
{{ definitions[category]['name'] }}
{{ underline * definitions[category]['name']|length }}

{% if definitions[category]['showcontent'] %}
{% for text, values in sections[section][category].items() %}
* {{ text }} ({% for value in values -%}
                 {{ reference(value) }}
                 {%- if not loop.last %}, {% endif -%}
              {%- endfor %}).
{% endfor %}
{% elif category == "migration" %}
This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head

{% else %}
* {{ sections[section][category]['']|sort|join(', ') }}

{% endif %}
{% if sections[section][category]|length == 0 %}
No significant changes.

{% else %}
{% endif %}

{% endfor %}
{% if sections[section]["author"] %}
{{definitions['author']["name"]}}
{{ underline * definitions['author']['name']|length }}

The following developers contributed to this release of Bodhi:

{% for text, values in sections[section]["author"].items() %}
* {{ text }}
{% endfor %}
{% endif %}

{% else %}
No significant changes.


{% endif %}
{% endfor %}

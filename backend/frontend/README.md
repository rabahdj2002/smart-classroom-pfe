# HeisenHelmet - Static Frontend

This version contains only HTML and CSS. All React, Babel, inline event handlers, and JavaScript files have been removed so the markup can be copied into Django templates and wired to Django views/forms later.

## Structure

```text
frontend/
├── index.html
└── css/
    └── styles.css
```

## Django Integration

Use `index.html` as the source for your Django template markup. Move `css/styles.css` into your Django static files directory, then replace the stylesheet link with Django's static helper:

```html
{% load static %}
<link rel="stylesheet" href="{% static 'css/styles.css' %}">
```

The current data is static placeholder content. Replace table rows, cards, and form values with Django template variables or loops as you connect real models.

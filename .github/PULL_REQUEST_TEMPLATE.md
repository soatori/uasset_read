name: Pull Request
description: Guidelines for submitting a pull request

body:
  - type: markdown
    attributes:
      value: |
        Thanks for contributing! Please fill out the template below.

  - type: textarea
    id: description
    attributes:
      label: Description
      description: What does this PR do?
    validations:
      required: true

  - type: textarea
    id: testing
    attributes:
      label: Testing
      description: How did you test this change?
    validations:
      required: true

  - type: checkboxes
    id: checklist
    attributes:
      label: Checklist
      options:
        - label: Tests pass (`python -m pytest tests/ -v`)
          required: true
        - label: Code follows project style
          required: true
        - label: New tests added (if applicable)
          required: false

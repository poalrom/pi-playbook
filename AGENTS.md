# Repository Guidelines

## Verification

- Do not add automated tests or test suites to this repository.
- Verify Ansible changes with syntax checks, template rendering, linting when
  available, and focused inspection of the generated configuration.
- Run deployment or live service checks only when the user explicitly
  authorizes changes to the target host.

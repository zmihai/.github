# Contributing to .github Repository

Thank you for contributing to our common workflows and actions repository!

## 📋 Guidelines

### Adding a New Reusable Workflow

1. Create the workflow file in `.github/workflows/` with prefix `reusable-`
2. Use `workflow_call` trigger
3. Document all inputs, outputs, and secrets
4. Add usage examples in the README
5. Test the workflow in a test repository

### Adding a New Composite Action

1. Create a new directory in `actions/` with a descriptive name
2. Create `action.yml` with comprehensive metadata:
   - Name, description, and author
   - All inputs with descriptions and defaults
   - All outputs with descriptions
   - Branding (icon and color)
3. Add usage examples in the README
4. Test the action in a test repository

### Adding a Workflow Template

1. Create the template file in `workflow-templates/`
2. Create a corresponding `.properties.json` file
   - `filePatterns` entries are **regexes** matched against repo file paths. Escape literal dots (`package\.json$`) and keep them **unanchored** (no leading `^`) so marker files in monorepo subdirectories still match.
   - If the template supports new languages, add the ecosystem's marker file(s) to `filePatterns` and update `tests/test_workflow_templates.py` to keep the assertions in sync.
3. Ensure it uses reusable workflows when possible
4. Add clear comments and documentation

> Templates are served from the default branch, so they don't need a version bump/tag to take effect.

## 🧪 Testing

Before submitting:

1. Test workflows in a separate test repository
2. Verify all inputs work as expected
3. Check that secrets are handled securely
4. Ensure documentation is accurate

## 📝 Documentation

- Update README.md with new workflows/actions
- Include usage examples
- Document all parameters
- Add troubleshooting tips if needed

## 🔒 Security

- Never commit secrets or credentials
- Use GitHub Secrets for sensitive data
- Follow least privilege principle for permissions
- Review security scan results

## 🎯 Best Practices

- Keep workflows focused and single-purpose
- Make workflows configurable with inputs
- Provide sensible defaults
- Use latest stable versions of actions
- Add proper error handling

Thank you for helping improve our workflows and actions!

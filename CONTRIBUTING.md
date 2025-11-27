CONTRIBUTION GUIDELINES
===========================

Purpose
-------
This file documents how new developers should set up and contribute to this project locally. It includes installation steps

Prerequisites
-------------
- Node.js (v14+ recommended) and `npm`/`npx` installed.
- Git available in PATH.

Quick local install (dev dependencies)
------------------------------------
From the repository root run:

```bash
npm install 
```

# Contribution Guidelines

## Branch Strategy

We use a three-tier branching model:

- **`main`** (production) - Production-ready code, protected branch
- **`staging`** - Pre-production testing environment
- **`development`** - Active development branch
- **`feature/*`** - Individual feature branches
- **`fix/*`** - Individual feature branches

## Development Workflow

1. **Create a feature branch** from `development`:
   ```bash
   git checkout development
   git pull origin development
   git checkout -b feature/your-feature-name
   ```

2. **Develop your feature** following our coding standards
   - Write clean, tested code
   - Follow the [Conventional Commits format](#commitlint)
   - Run code formatting before committing

3. **Submit a Pull Request**:
   - Create a PR from `feature/your-feature-name` → `development`
   - The team captain will review your code
   - Address any review comments
   - Once approved, your feature will be merged into `development`

4. **Promotion between branches**:
   - `development` → `staging`: When features are ready for testing
   - `staging` → `main`: When staging is stable and ready for production

## Branch Naming Convention

- Features: `feature/feature-name` (e.g., `feature/user-authentication`)
- Bug fixes: `fix/bug-description` (e.g., `fix/login-error`)

## Pull Request Process

1. Ensure your code passes all CI checks (formatting, security)
2. Provide a clear description of what your PR does
3. Link any related issues
4. Request review from the team captain
5. Wait for approval before merging

## Important Notes

- **Never commit directly to `main`, `staging`, or `development`**
- Always work in feature branches
- Keep your feature branch up to date with `development`
- Delete your feature branch after it's merged

## Commitlint
- **feat:** a new feature
- **fix:** a bug fix
- **docs:** documentation only changes
- **style:** formatting, missing semi-colons, no production code change
- **refactor:** code change that neither fixes a bug nor adds a feature
- **perf:** code change that improves performance
- **test:** adding or changing tests
- **build:** changes that affect the build system or external dependencies
- **ci:** CI configuration and scripts
- **chore:** other changes that don't modify src or tests (see below)

Examples:

- `feat(auth): add JWT token support`
- `fix(api): return 404 for missing user`
- `chore: refresh lockfile`


# Contributing to Grassday

Thank you for your interest in contributing to Grassday! Since this is an open-source Hackathon project designed around minimal screen time, contributions that align with our "Living Nature" philosophy are highly encouraged.

## How to Contribute
1. **Fork the repo.**
2. **Create a branch** for your feature (`git checkout -b feature/amazing-feature`).
3. **Commit your changes** (`git commit -m 'Add amazing feature'`).
4. **Push to the branch** (`git push origin feature/amazing-feature`).
5. **Open a Pull Request.**

## Development Setup
- Backend: Python 3.11+
- Frontend: Node.js 18+

Use the provided `Makefile` to quickly spin up the development environment:
```bash
make setup
make backend
make frontend
```

## Guidelines
- **No telemetry.** We respect privacy. All data stays local.
- **Keep it offline-first.** Features should gracefully degrade if network APIs are unavailable.
- **Write tests.** Ensure `make test` passes before submitting a PR.
- **Theme adherence.** UI contributions should match the Glassmorphism/Liquid aesthetic defined in `frontend/src/index.css`.

Happy hacking! 🌿

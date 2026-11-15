# Native C++ netucs

See [MIGRATION.md](MIGRATION.md) for C++ and Python examples, installation,
protocol compatibility, tests and documented limitations.

### Conductor dependency

Install Conductor's C++ development headers and library separately before
building netucs. netucs does not embed or rebuild Conductor. If installed in a
nonstandard prefix, configure `CONDUCTOR_INCLUDE_DIR` and `CONDUCTOR_LIBRARY`.

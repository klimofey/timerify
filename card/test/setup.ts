// Runs before every test file. The tests use Lit's development build on purpose, for the
// warnings it raises about mistakes in a component; this only silences the notice that it
// is a development build, which would otherwise be printed once in every test file.
const lit = globalThis as { litIssuedWarnings?: Set<string> };
lit.litIssuedWarnings ??= new Set();
lit.litIssuedWarnings.add("dev-mode");

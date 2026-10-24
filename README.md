# dosho

*A shinobi's tool bag.*

`dosho` is the native cab repository for
[shinobi](https://github.com/shinobi-dosho/stimela-ninja) (stimela-ninja,
Stimela 3.0). A tool is one of two shapes: a real binary is a YAML
*document*, exposed as a `CabSpec`; a Python-package tool
with no standalone binary (for example, CASA tasks) is an ordinary annotated
function marked with `@dosho.pystep`. Shinobi adapts either when a recipe uses
it. A cab is parameter configuration and stays declarative whatever
carries it, so there's no `dynamic_schema`-style Python-execution step at
cab-load time, no expression language, and no dtype coverage gaps.

## Academic attribution

Please acknowledge this project and its contributors when using the work
in research, and cite the associated publications and software release
where applicable. This is a scholarly request, not an additional licence
condition.
Citation information can be found in [CITATION.cff](CITATION.cff).

## Installing

```
# Catalogue data only
pip install "dosho>=0.2.0b1,<0.3"
# Standalone schemas and argv
pip install "dosho[validation]>=0.2.0b1,<0.3"
# Runnable cabs and recipes from matching candidate checkouts
pip install -e "/path/to/dosho[validation]" -e /path/to/stimela-ninja
```

The definitions are data — YAML documents under `dosho/documents/`, readable
without the framework. `dosho.cabs.<tool>`, `dosho.get(...)` and
`dosho.define_cab(...)` expose definitions without importing Shinobi.
Listing names and reading raw documents need neither Pydantic nor Shinobi;
definition building, Python schemas and argv formatting need `dosho[validation]`.
Shinobi depends on that extra and constructs runtime `Cab`/`StepRef` objects
when a recipe uses a definition. The retired `dosho[run]` extra is no longer needed.
Pin a source commit for reproducibility. After Ninja's beta is published,
`stimela-ninja>=0.2.0b1,<0.3` can be installed from PyPI instead.

Since v0.2.0b1, Dosho owns schema compilation, parameter metadata, policies,
patterns and validated argv formatting. Shinobi owns framework annotations,
DAG wiring, execution, filesystem enforcement and dataset lifecycle. See
[validation and migration](https://dosho.readthedocs.io/en/latest/concepts/validation.html)
for the standalone API and compatibility boundary.

## Usage

Know the tool at write-time? Import it directly:

```python
from dosho.cabs import wsclean
from dosho.cabs.casatasks import listobs
```

Only know the name at runtime? Use the string-keyed registry:

```python
import dosho

wsclean = dosho.get("wsclean")
```

Both definitions can be passed directly to `Recipe.add_step`. For a runtime
object outside a recipe, use `shinobi.cabs.get("wsclean")` or
`shinobi.cabs.adapt_definition(wsclean)`. These APIs require matching Shinobi
and Dosho sources for the neutral-definition boundary described here.

Or, from shinobi itself (any installed `shinobi.cabs`-entry-point
provider, `dosho` included):

```console
$ ninja cabs list
$ ninja cabs show wsclean
```

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

# dosho

*A shinobi's tool bag.*

`dosho` is the native cab repository for
[shinobi](https://github.com/shinobi-dosho/stimela-ninja) (stimela-ninja,
Stimela 3.0). A tool is one of two shapes: a real binary is a YAML
*document*, built into a `shinobi.Cab` on demand; a Python-package tool
with no standalone binary (for example, CASA tasks) is a `@shinobi.pystep`-produced
`StepRef`. A cab is parameter configuration and stays declarative whatever
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
# Runnable cabs and recipes, pending Ninja's v0.2 beta publication
pip install "stimela-ninja @ git+https://github.com/shinobi-dosho/stimela-ninja.git@main"
```

The definitions are data — YAML documents under `dosho/documents/`, readable
without the framework. `dosho.cabs.<tool>` and `dosho.get(...)` turn one into a
`Cab`, which needs an explicit Shinobi installation. Shinobi depends on
`dosho[validation]`; the retired `dosho[run]` extra is no longer needed.
Base catalogue access needs neither Pydantic nor Shinobi, and validation
needs Pydantic but never imports Shinobi.
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

Or, from shinobi itself (any installed `shinobi.cabs`-entry-point
provider, `dosho` included):

```console
$ ninja cabs list
$ ninja cabs show wsclean
```

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

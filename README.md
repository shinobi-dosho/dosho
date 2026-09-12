# dosho

Please acknowledge this project and its contributors when using the work
in research, and cite the associated publications and software release
where applicable. This is a scholarly request, not an additional licence
condition.

*A shinobi's tool bag.*

`dosho` is the native cab repository for
[shinobi](https://github.com/shinobi-dosho/stimela-ninja) (stimela-ninja,
Stimela 3.0). A tool is one of two shapes: a real binary is a YAML
*document*, built into a `shinobi.Cab` on demand; a Python-package tool
with no standalone binary (CASA tasks, simms 3.0's
`skysim`/`telsim`/`primary-beam`) is a `@shinobi.pystep`-produced
`StepRef`. A cab is parameter configuration and stays declarative whatever
carries it, so there's no `dynamic_schema`-style Python-execution step at
cab-load time, no expression language, and no dtype coverage gaps.

## Installing

```
pip install dosho          # the cab definitions: names, schemas, images
pip install dosho[run]     # ...plus stimela-ninja, to build and run them
```

The definitions are data — YAML documents under `dosho/documents/`, readable
without the framework. `dosho.cabs.<tool>` and `dosho.get(...)` turn one into a
`Cab`, which needs the `run` extra.

See [`AGENTS.md`](./AGENTS.md) for the design rationale and
tool-authoring conventions.

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

## Status

`dosho` currently hosts 61 real-binary `Cab`s (`wsclean`, `cubical`,
`quartical`, `ddfacet`, `killms`, `aoflagger`, `tricolour`, `crystalball`,
`shadems`, `ragavi`, `sofia2`, `mosaic-queen`, classic `simms`, ...) and 68
`@shinobi.pystep` wrappers around Python-package tools with no standalone
binary -- CASA tasks (`listobs`, `mstransform`, `gaincal`, `bandpass`,
`applycal`, `tclean`, ...) and simms 3.0's `skysim`/`telsim`/`primary-beam`
(pysteps as of simms 3.0, no longer a `simms` sub-command binary) -- the
set a real pipeline
([caracal2](https://github.com/caracal-pipeline/caracal2)) needs.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

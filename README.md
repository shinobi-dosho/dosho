# dosho

*A shinobi's tool bag.*

`dosho` is the native cab repository for
[shinobi](https://github.com/SpheMakh/stimela-ninja) (stimela-ninja,
Stimela 3.0). Every tool is authored directly in Python -- a
`shinobi.Cab` object for a real binary, or a `@shinobi.pystep`-produced
`StepRef` for a Python-package tool with no standalone binary (CASA tasks,
simms 3.0's `skysim`/`telsim`/`primary-beam`) -- instead of a YAML dialect,
so there's no `dynamic_schema`-style Python-execution step at cab-load time
and no dtype coverage gaps.

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

`dosho` currently hosts 42 real-binary `Cab`s (`wsclean`, `cubical`,
`quartical`, `ddfacet`, `killms`, `aoflagger`, `tricolour`, `crystalball`,
`shadems`, `ragavi`, `sofia2`, `mosaic-queen`, classic `simms`, ...) and 62
`@shinobi.pystep` wrappers around Python-package tools with no standalone
binary -- CASA tasks (`listobs`, `mstransform`, `gaincal`, `bandpass`,
`applycal`, `tclean`, ...) and simms 3.0's `skysim`/`telsim`/`primary-beam`
(pysteps as of simms 3.0, no longer a `simms` sub-command binary) -- the
set a real pipeline
([caracal2](https://github.com/caracal-pipeline/caracal2)) needs.

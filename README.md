# dosho

*A shinobi's tool bag.*

`dosho` is the native cab repository for
[shinobi](https://github.com/SpheMakh/stimela-ninja) (stimela-ninja,
Stimela 3.0). Every tool is authored directly in Python -- a
`shinobi.Cab` object for a real binary, or a `@shinobi.pystep`-produced
`StepRef` for a Python-package tool with no standalone binary (CASA
tasks) -- instead of a YAML dialect, so there's no `dynamic_schema`-style
Python-execution step at cab-load time and no dtype coverage gaps.

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

`dosho` currently hosts 12 real-binary `Cab`s (`wsclean`, `cubical`,
`quartical`, `aoflagger`, `tricolour`, `crystalball`, `owlcat_plotelev`,
`shadems`, `ragavi`, `sofia2`, `simms` skysim, `mosaic-queen`) and 14
`@shinobi.pystep` CASA-task wrappers (`listobs`, `mstransform`, `fixvis`,
`clearcal`, `initweights`, `flagdata`, `setjy`, `gaincal`, `polcal`,
`bandpass`, `applycal`, `fluxscale`, `flagmanager`, `plotms`) -- the set
a real pipeline ([caracal2](https://github.com/caracal-pipeline/caracal2))
needs. `simms`'s other two sub-commands (`telsim`, `simms`) aren't ported
yet.

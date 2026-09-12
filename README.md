# dosho

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

## Academic ethinal standards apply
Please acknowledge this project and its contributors when using the work
in research, and cite the associated publications and software release
where applicable. This is a scholarly request, not an additional licence
condition. Citation information can be found in [CITIATION](link-to-citation-md).


## Installing

```
pip install dosho          # the cab definitions: names, schemas, images
pip install dosho[run]     # ...plus stimela-ninja, to build and run them
```

The definitions are data — YAML documents under `dosho/documents/`, readable
without the framework. `dosho.cabs.<tool>` and `dosho.get(...)` turn one into a
`Cab`, which needs the `run` extra.

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

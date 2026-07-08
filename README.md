# dosho

*A shinobi's tool bag.*

`dosho` is the native cab repository for
[shinobi](https://github.com/SpheMakh/stimela-ninja) (stimela-ninja,
Stimela 3.0). Cabs are authored directly in Python -- `shinobi.Cab`
objects built with shinobi's existing typed schema machinery -- instead of
a YAML dialect, so there's no `dynamic_schema`-style Python-execution step
at cab-load time and no dtype coverage gaps.

See [`AGENTS.md`](./AGENTS.md) for the design rationale and cab-authoring
conventions.

## Usage

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

Early scaffold -- the first cabs being ported are `wsclean` and `cubical`
(the two with the worst existing cult-cargo-loader workarounds), followed
by `quartical` and the remaining flat cabs a real pipeline
([caracal2](https://github.com/caracal-pipeline/caracal2)) needs.

# Dosho

*A shinobi's tool bag.*

**Dosho** provides ready-made tool definitions for radio astronomy pipelines,
including WSClean, CASA tasks, CubiCal, QuartiCal and AOFlagger.
Use them with [Stimela Ninja](https://stimela-ninja.readthedocs.io/)
to build a pipeline without describing each tool's command-line options yourself.

Each definition is called a **cab**. It describes a tool's inputs, outputs
and container image. Dosho supplies the definitions; Stimela Ninja runs the tools.

## Get started

You can [browse the tool catalogue](https://dosho.readthedocs.io/en/latest/reference/cabs.html)
without installing anything.

To use the tools in a pipeline, install Stimela Ninja. It includes Dosho.
You need Python 3.11 or newer:

```bash
pip install "stimela-ninja>=0.2.0b1"
ninja cabs list
ninja cabs show wsclean
```

These commands list available tools and show WSClean's parameters; they do
not run WSClean or need astronomy data. The astronomy software itself runs
separately, in a container or from an installation on your computer.

Follow the [installation guide](https://dosho.readthedocs.io/en/latest/installation.html)
for environment setup and tool requirements, then the
[quickstart](https://dosho.readthedocs.io/en/latest/quickstart.html) to use a cab
in a recipe.

## Use definitions in Python

With Stimela Ninja installed, you can import a tool definition:

```python
from dosho.cabs import wsclean
```

Pass it to `Recipe.add_step` when building a pipeline. The quickstart shows
a complete example.

To inspect definitions with Dosho alone:

```bash
pip install "dosho[validation]>=0.2.0b2"
dosho list
dosho show wsclean
dosho validate my-cabs.yaml
```

`list` needs only the base package. `show` reads schemas, and `validate`
checks static definitions and native parameter defaults. Framework types and
access/family declarations are labelled `requires stimela-ninja to validate`.
Add `--strict` to `validate` to fail if any checks remain deferred.
These checks do not qualify data or execute tools.

Dosho also works on its own. See the
[standalone installation options](https://dosho.readthedocs.io/en/latest/installation.html#for-using-dosho-on-its-own)
for browsing definitions and checking parameters without Stimela Ninja, or
[authoring cabs](https://dosho.readthedocs.io/en/latest/concepts/authoring.html)
to add a tool.

## Academic attribution

Please acknowledge this project and its contributors when using the work
in research, and cite the associated publications and software release
where applicable. This is a scholarly request, not an additional licence
condition.
Citation information can be found in [CITATION.cff](CITATION.cff).

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

# CASA site configuration baked into the dosho casa6 image and selected via the
# CASASITECONFIG env var. Read on every casatools/casatasks/casaplotms import.
#
# measurespath points at the measures/ephemeris data we pre-download at build
# time; the *_auto_update flags disable CASA's runtime network updates so imports
# are deterministic and offline (and never need a user-owned, writable data dir,
# which matters under singularity/apptainer where the container runs as the
# invoking uid rather than root).
measurespath = "/opt/casa/data"
measures_auto_update = False
data_auto_update = False

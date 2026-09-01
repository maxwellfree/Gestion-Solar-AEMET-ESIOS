# Installation and Configuration

## Predictive Solar Energy Management --- Setup Guide

This document explains how to install, configure, and run **Predictive
Solar Energy Management**.

The project currently combines **AEMET OpenData** for weather
forecasting, **PVGIS** for solar and climatological reference data,
**ESIOS** for economic information, a configurable household-demand
model, and a sustainable storage and dispatch model.

> **Project status:** experimental software. Optimizer recommendations
> do not replace electrical protections, the battery BMS, inverter
> internal limits, or manufacturer instructions.

------------------------------------------------------------------------

# 1. Installation Methods

There are currently two main installation methods:

1.  **`.deb` package** --- recommended for Ubuntu and Debian.
2.  **`installation/install.sh`** --- installation directly from the
    GitHub repository.

A manual installation procedure is also retained for development and
debugging.

A household installation should no longer be configured by manually
editing `config.py` and `demand.py`. The system now uses:

``` text
wizard.py
    │
    ▼
config.yaml
    │
    ├──► config.py
    └──► demand.py
```

`config.yaml` is the persistent configuration entered by the user. The
wizard automatically generates `config.py` and `demand.py` while
preserving the interfaces expected by the rest of the application.

------------------------------------------------------------------------

# 2. General Requirements

The system requires:

``` text
Linux
Python 3
Internet connection
AEMET OpenData API key
ESIOS token
```

PVGIS does not normally require personal credentials for the public
queries currently used by the project.

It is advisable to obtain the **AEMET** and **ESIOS** credentials before
starting configuration because the installer requests them.

------------------------------------------------------------------------

# 3. Recommended Ubuntu/Debian Method: `.deb` Package

## 3.1 Download

Published Debian packages are distributed through the **GitHub
Releases** section of the repository:

``` text
https://github.com/maxwellfree/Gestion-Solar-AEMET-ESIOS
```

After downloading a package, for example:

``` text
gestion-solar-predictiva_VERSION_all.deb
```

open a terminal in the directory containing it.

## 3.2 Install

Run:

``` bash
sudo apt install ./gestion-solar-predictiva_VERSION_all.deb
```

`apt` will resolve the system dependencies declared by the package.

> `sudo` is used to install the `.deb`, but **must not be used to run
> `gestion-solar-config` or `gestion-solar`**.

## 3.3 Configure

After installation, run:

``` bash
gestion-solar-config
```

This command prepares the user's private application area and requests
the required credentials.

Personal configuration is normally stored under:

``` text
~/.local/share/gestion-solar/
```

This directory contains files such as:

``` text
config.yaml
config.py
demand.py
mytoken.env
```

Credentials belong to the user and are not included in the `.deb`
package.

## 3.4 Run

A first test can be performed with:

``` bash
gestion-solar --soc 0.60
```

where `0.60` represents an initial SOC of 60%.

A successful execution displays information about the PV system, demand
model, weather forecast, predicted PV generation, energy balance,
economics, sustainable dispatch, and management plan.

------------------------------------------------------------------------

# 4. Installation from GitHub Using `install.sh`

This method is appropriate for development, testing, and direct
installation from source.

## 4.1 Clone the Repository

``` bash
git clone https://github.com/maxwellfree/Gestion-Solar-AEMET-ESIOS.git
cd Gestion-Solar-AEMET-ESIOS
```

## 4.2 Run the Installer

Make the installer executable if necessary:

``` bash
chmod +x installation/install.sh
```

Then run:

``` bash
./installation/install.sh
```

Do not run the complete installer as:

``` bash
sudo ./installation/install.sh
```

The installer itself may request elevated privileges for a specific
system operation when required.

## 4.3 Installation Flow

The general installation sequence is:

``` text
system detection
        │
        ▼
Python detection
        │
        ▼
create/check .venv
        │
        ▼
install dependencies
        │
        ▼
credentials
        │
        ▼
wizard.py
        │
        ▼
config.yaml
        │
        ├──► config.py
        └──► demand.py
```

For older Python versions, the installer may use:

``` text
installation/requirements-legacy.txt
```

The installer avoids using `sudo pip`.

------------------------------------------------------------------------

# 5. Files Required by `install.sh`

Users installing from GitHub should clone or download the complete
repository.

The relevant structure is:

``` text
Gestion-Solar-AEMET-ESIOS/
│
├── README.md
├── LICENSE
├── requirements.txt
│
├── main.py
├── config.py
├── demand.py
├── aemet.py
├── aemet_hourly.py
├── aemet_planificador.py
├── solar.py
├── esios.py
├── esios_client.py
├── esios_prices.py
├── balance.py
├── dispatch.py
├── optimizer.py
├── weekly.py
├── municipios.py
├── gestion_solar.py
│
├── installation/
│   ├── install.sh
│   ├── wizard.py
│   ├── requirements-legacy.txt
│   └── templates/
│       ├── config.py.tpl
│       └── demand.py.tpl
│
└── docs/
```

Personal configuration and secrets must not be distributed, including:

``` text
mytoken.env
config.yaml
.venv/
__pycache__/
```

------------------------------------------------------------------------

# 6. The `wizard.py` Configuration Assistant

`wizard.py` describes a particular installation. It can configure, among
other parameters:

-   installation name;
-   province, municipality, and AEMET municipality code;
-   number and rated power of PV modules;
-   tilt and azimuth;
-   inverter;
-   batteries and storage capacity;
-   SOC operating windows;
-   efficiencies;
-   number of adults and children;
-   energy-management preferences;
-   household loads;
-   load flexibility and automation;
-   presence requirements;
-   allowed operating windows;
-   control strategy.

At completion it generates:

``` text
config.yaml
config.py
demand.py
```

------------------------------------------------------------------------

# 7. Keeping an Existing Configuration

If `wizard.py` finds an existing:

``` text
config.yaml
```

it asks whether the user wants to keep that configuration.

If the existing configuration is retained:

``` text
existing config.yaml
        │
        ▼
automatic regeneration
    ├── config.py
    └── demand.py
```

The user does not need to enter all installation data again.

If the configuration is not retained, the wizard runs the questionnaire
again and writes a new configuration.

------------------------------------------------------------------------

# 8. Role of `config.yaml`, `config.py`, and `demand.py`

`config.yaml` contains the persistent installation-specific
configuration.

`config.py` and `demand.py` are generated to preserve compatibility with
the existing application core.

For a normal user:

``` text
DO NOT manually edit config.py
DO NOT manually edit demand.py

reconfigure through wizard.py
```

The generation templates are:

``` text
installation/templates/config.py.tpl
installation/templates/demand.py.tpl
```

These templates are part of the source code and should be kept in
GitHub.

------------------------------------------------------------------------

# 9. Credentials

The project currently requires credentials for:

``` text
AEMET OpenData
ESIOS
```

They are stored locally in:

``` text
mytoken.env
```

using variables equivalent to:

``` text
AEMET_API_KEY=...
ESIOS_API_KEY=...
```

Real credentials must never be included in GitHub, `.deb` packages,
documentation, public screenshots, or example files.

The credentials file should be private:

``` bash
chmod 600 mytoken.env
```

For a `.deb` installation it is normally located at:

``` text
~/.local/share/gestion-solar/mytoken.env
```

Check it with:

``` bash
ls -l ~/.local/share/gestion-solar/mytoken.env
```

The file must belong to the user running the application.

------------------------------------------------------------------------

# 10. AEMET OpenData

AEMET supplies weather information used by the prediction model,
including temperature, sky conditions, precipitation, and daily and
hourly forecasts.

Related modules include:

``` text
aemet.py
aemet_hourly.py
solar.py
weekly.py
```

Portal:

``` text
https://opendata.aemet.es/
```

Request an API key:

``` text
https://opendata.aemet.es/centrodedescargas/altaUsuario
```

Developer documentation:

``` text
https://opendata.aemet.es/centrodedescargas/AEMETApi
```

Conceptually, the project uses municipal endpoints such as:

``` text
/api/prediccion/especifica/municipio/diaria/{municipio}
/api/prediccion/especifica/municipio/horaria/{municipio}
```

AEMET may temporarily rate-limit requests, for example with `HTTP 429`.
Duplicate requests should be avoided and downloaded responses should be
reused whenever possible.

------------------------------------------------------------------------

# 11. PVGIS

PVGIS provides the physical and climatological reference used by the
photovoltaic model:

``` text
PVGIS + AEMET → PV prediction
```

Web tool:

``` text
https://re.jrc.ec.europa.eu/pvg_tools/en/
```

API:

``` text
https://re.jrc.ec.europa.eu/api/
```

The public queries currently used by the project do not normally require
personal credentials.

The application may use cache files such as:

``` text
.solar_pvgis_cache.json
.solar_location_cache.json
```

------------------------------------------------------------------------

# 12. ESIOS

ESIOS provides economic information used for hourly prices and energy
planning.

Portal:

``` text
https://www.esios.ree.es/
```

API:

``` text
https://api.esios.ree.es/
```

The personal token must remain outside the repository and distribution
packages.

------------------------------------------------------------------------

# 13. First Test

## `.deb` Installation

``` bash
gestion-solar --soc 0.60
```

## Source Installation

``` bash
source .venv/bin/activate
python3 main.py --soc 0.60
```

A more complete source execution can use:

``` bash
python3 main.py \
    --soc 0.60 \
    --mostrar-semanal \
    --mostrar-precios \
    --mostrar-solar \
    --mostrar-balance \
    --mostrar-plan-horario
```

The command-line option names are currently kept in Spanish because they
are part of the software interface.

The program header should reflect the values entered in the wizard:
municipality, number of modules, installed PV power, inverter,
batteries, storage capacity, SOC limits, occupants, and loads.

------------------------------------------------------------------------

# 14. Reconfiguration

With the `.deb` installation:

``` bash
gestion-solar-config
```

From the GitHub source tree:

``` bash
source .venv/bin/activate
python3 installation/wizard.py
```

If `config.yaml` already exists, it can be retained to regenerate
`config.py` and `demand.py` directly.

------------------------------------------------------------------------

# 15. Common Problems

## `ModuleNotFoundError`

For a source installation:

``` bash
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

When using the `.deb`, activating the repository's `.venv` should not be
necessary.

## Permission Denied for `mytoken.env`

An error such as:

``` text
PermissionError: [Errno 13] Permission denied: '.../mytoken.env'
```

usually indicates incorrect ownership.

Check:

``` bash
ls -l ~/.local/share/gestion-solar/mytoken.env
```

If the file accidentally belongs to `root`, replace `USER` with the
actual account name:

``` bash
sudo chown -R USER:USER ~/.local/share/gestion-solar
chmod 700 ~/.local/share/gestion-solar
chmod 600 ~/.local/share/gestion-solar/mytoken.env
```

Then run Predictive Solar Energy Management **without `sudo`**.

## AEMET API-Key Error

Inspect `mytoken.env` locally without publishing or sharing the
credential value.

## AEMET Rate Limiting

Wait and retry. Avoid launching multiple identical requests from
different modules.

## ESIOS Returns No Data

Check:

-   token;
-   endpoint;
-   requested dates;
-   request headers;
-   availability of the indicator being used.

## Incorrect Municipality

Run the wizard again and verify the province, municipality, and AEMET
code.

## Unusual PV Prediction

Review:

-   location;
-   tilt;
-   azimuth;
-   number and rated power of modules;
-   inverter maximum power;
-   weather source;
-   PVGIS cache.

------------------------------------------------------------------------

# 16. Manual Installation for Development

``` bash
git clone https://github.com/maxwellfree/Gestion-Solar-AEMET-ESIOS.git
cd Gestion-Solar-AEMET-ESIOS

python3 -m venv .venv
source .venv/bin/activate

python3 -m pip install -r requirements.txt
python3 installation/wizard.py
python3 main.py --soc 0.60
```

For normal users, the `.deb` package or `installation/install.sh` is
recommended instead.

------------------------------------------------------------------------

# 17. Files That Must Not Be Uploaded to GitHub

The `.gitignore` should exclude at least:

``` gitignore
# Credentials
mytoken.env
.env
*.env

# Installation-specific configuration
config.yaml

# Python environments
.venv/
venv/

# Python
__pycache__/
*.pyc
*.pyo

# Output
output.txt
*.log

# Local backups
backup/
seguridad/

# Compiled packages
*.deb
```

`.deb` packages should preferably be distributed through **GitHub
Releases** rather than stored as binaries in the main repository tree.

------------------------------------------------------------------------

# 18. Checking for Accidentally Published Secrets

Before committing:

``` bash
git status
```

A preventive search can also be performed:

``` bash
grep -RniE \
    'api[_-]?key|token|password|passwd|secret|authorization' \
    . \
    --exclude-dir=.git \
    --exclude-dir=.venv
```

The presence of names such as `API_KEY` in source code does not by
itself indicate a leaked secret. Check that no **real credential value**
is present.

If a real credential has ever been committed, deleting it from the
current file is not sufficient. It should be revoked or regenerated.

------------------------------------------------------------------------

# 19. Reproducibility

For experiments and validation, preserve:

``` text
software version
Git commit
configuration
date
initial SOC
weather forecast
PVGIS data
prices
strategy
result
```

Credentials are never required to reproduce a scientific result.

------------------------------------------------------------------------

# 20. Home Assistant and Future Integration

Home Assistant is not required to run the current model.

It may later be used as a user interface, dashboard, notification
system, real-data acquisition layer, load-automation platform, and
equipment-integration layer.

Communication with an inverter should remain in an independent layer.

Recommended progression:

``` text
PHASE 1  simulation
PHASE 2  real data without control
PHASE 3  shadow mode
PHASE 4  automation of non-critical loads
PHASE 5  limited inverter control
PHASE 6  closed-loop predictive control
```

Before enabling register writes, SOC changes, operating-mode changes, or
charge/discharge commands, the system should undergo experimental
validation and include an independent safety layer.

------------------------------------------------------------------------

# 21. Safety

This project is experimental.

Optimizer decisions do not replace:

-   electrical protections;
-   the BMS;
-   internal inverter limits;
-   AC/DC protections;
-   manufacturer safety mechanisms.

The conceptual separation should be:

``` text
prediction
    ↓
optimization
    ↓
recommendation
    ↓
safety layer
    ↓
eventual actuation
```

A software recommendation must not automatically be interpreted as a
safe hardware command.

------------------------------------------------------------------------

# 22. Related Documentation

``` text
docs/
├── INSTALLATION.md
├── INSTALLATIONen.md
├── MODEL.md
├── MODELen.md
├── DISPATCH.md
├── DISPATCHen.md
├── WEEKLY.md
├── WEEKLYen.md
├── VALIDATION.md
├── VALIDATIONen.md
├── ARCHITECTURE.md
└── ARCHITECTUREen.md
```

The Spanish documents retain the original filenames, while English
companion documents use the `en` suffix.

------------------------------------------------------------------------

# 23. Quick Start

## Ubuntu/Debian

``` bash
sudo apt install ./gestion-solar-predictiva_VERSION_all.deb
gestion-solar-config
gestion-solar --soc 0.60
```

## GitHub

``` bash
git clone https://github.com/maxwellfree/Gestion-Solar-AEMET-ESIOS.git
cd Gestion-Solar-AEMET-ESIOS
chmod +x installation/install.sh
./installation/install.sh
```

## Reconfigure

Debian package:

``` bash
gestion-solar-config
```

Source code:

``` bash
python3 installation/wizard.py
```

The installation-specific configuration is preserved in `config.yaml`;
`config.py` and `demand.py` are generated automatically to maintain
compatibility with the current application core.

# Care Demo Facility Setup

This plug helps setup a demo facility with a hel

## Local Development

To develop the plug in local environment along with care, follow the steps below:

1. Go to the care root directory and clone the plugin repository:

```bash
cd care
git clone git@github.com:ohcnetwork/Care Demo Facility Setup.git
```

2. Add the plugin config in plug_config.py

```python
...

Care Demo Facility Setup_plugin = Plug(
    name=Care Demo Facility Setup, # name of the django app in the plugin
    package_name="/app/Care Demo Facility Setup", # this has to be /app/ + plugin folder name
    version="", # keep it empty for local development
    configs={}, # plugin configurations if any
)
plugs = [Care Demo Facility Setup_plugin]

...
```

3. Tweak the code in plugs/manager.py, install the plugin in editable mode

```python
...

subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "-e", *packages] # add -e flag to install in editable mode
)

...
```

4. Rebuild the docker image and run the server

```bash
make re-build
make up
```

> [!IMPORTANT]
> Do not push these changes in a PR. These changes are only for local development.

## Production Setup

To install care Care Demo Facility Setup, you can add the plugin config in [care/plug_config.py](https://github.com/ohcnetwork/care/blob/develop/plug_config.py) as follows:

```python
...

Care Demo Facility Setup_plug = Plug(
    name=Care Demo Facility Setup,
    package_name="git+https://github.com/ohcnetwork/Care Demo Facility Setup.git",
    version="@master",
    configs={},
)
plugs = [Care Demo Facility Setup_plug]
...
```

[Extended Docs on Plug Installation](https://care-be-docs.ohc.network/pluggable-apps/configuration.html)



This plugin was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) using the [ohcnetwork/care-plugin-cookiecutter](https://github.com/ohcnetwork/care-plugin-cookiecutter).

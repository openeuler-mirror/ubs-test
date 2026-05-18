import tomllib

CONF = {}


def read_toml(file_path: str) -> dict:
    try:
        with open(file_path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError as e:
        raise Exception(f"Invalid toml file path: {file_path}.") from e
    except tomllib.TOMLDecodeError as e:
        raise tomllib.TOMLDecodeError(f"TOML load config failed - {e}")
    except Exception as e:
        raise Exception(f"Failed to load {file_path}, error: {str(e)}") from e


def init_config(path: str = None):
    global CONF
    CONF.clear()
    if path is None:
        path = "/etc/poc_tools/poc_tools.toml"
    CONF.update(read_toml(path))

"""CLI for gate devices."""
from enum import Enum, unique
from getpass import getpass
import json
import pprint
from typing import Any, Callable, Union, cast

import click
from typing_extensions import Final

from . import AbstractGateApi, GogoGate2Api, ISmartGateApi
from .common import EnhancedJSONEncoder

API: Final[str] = "api"
DEVICE_TYPE: Final[str] = "device_type"
PRETTY_PRINT: Final[pprint.PrettyPrinter] = pprint.PrettyPrinter(indent=4)


def _echo_response(obj: Any) -> None:
    click.echo(json.dumps(obj, indent=2, cls=EnhancedJSONEncoder))


@unique
class DeviceType(Enum):
    """Device types."""

    GOGOGATE2 = "gogogate2"
    ISMARTGATE = "ismartgate"


@unique
class Option(Enum):
    """CLI options."""

    HOST = "--host"
    USERNAME = "--username"
    PASSWORD = "--password"  # nosec
    DEVICE_TYPE = "--device-type"


@unique
class Command(Enum):
    """Device actions."""

    OPEN = "open"
    CLOSE = "close"
    INFO = "info"


@unique
class DoorArgument(Enum):
    """Door arguments."""

    DOOR_ID = "door_id"


def default_password() -> str:
    """Get the password from user input."""
    return getpass("Password: ").strip()


def get_context_api(ctx: click.core.Context) -> AbstractGateApi:
    """Get gate API from context."""

    return cast(AbstractGateApi, ctx.obj[API])


@click.group()
@click.option(Option.HOST.value, required=True)
@click.option(Option.USERNAME.value, required=True)
@click.option(
    Option.PASSWORD.value,
    default=default_password,
    help="Omit for interactive prompt. Use '-' to read from stdin.",
)
@click.option(
    Option.DEVICE_TYPE.value,
    required=True,
    type=click.Choice([item.value for item in DeviceType], case_sensitive=False),
    hidden=True,
)
@click.version_option()
@click.pass_context
def cli(
    ctx: click.core.Context, host: str, username: str, password: str, device_type: str,
) -> None:
    """Interact with the device API."""
    api_generator: Callable[[str, str, str], Union[GogoGate2Api, ISmartGateApi]]

    if device_type == DeviceType.GOGOGATE2.value:
        api_generator = GogoGate2Api
    else:
        api_generator = ISmartGateApi

    if password == "-":  # nosec
        password = default_password()

    ctx.obj = {API: api_generator(host, username, password)}


@cli.command(name=Command.INFO.value)
@click.pass_context
def info(ctx: click.core.Context) -> None:
    """Get info from device."""
    _echo_response(get_context_api(ctx).info())


@cli.command(name=Command.OPEN.value)
@click.argument(DoorArgument.DOOR_ID.value, type=int, required=True)
@click.pass_context
def open_door(ctx: click.core.Context, door_id: int) -> None:
    """Open the door."""
    _echo_response(get_context_api(ctx).open_door(door_id))


@cli.command(name=Command.CLOSE.value)
@click.argument(DoorArgument.DOOR_ID.value, type=int, required=True)
@click.pass_context
def close_door(ctx: click.core.Context, door_id: int) -> None:
    """Close the door."""
    _echo_response(get_context_api(ctx).close_door(door_id))


def cli_with_defaults(device_type: DeviceType) -> None:
    """Run command with default value."""
    cli(  # pylint: disable=no-value-for-parameter,unexpected-keyword-arg
        default_map={DEVICE_TYPE: device_type.value}
    )


def gogogate2_cli() -> None:
    """GogoGate2 entrypoint."""

    cli_with_defaults(DeviceType.GOGOGATE2)


def ismartgate_cli() -> None:
    """iSmartGate entrypoint."""
    cli_with_defaults(DeviceType.ISMARTGATE)


def maybe_init() -> None:
    """Initialize the main function if needed."""

    if __name__ == "__main__":
        cli()  # pylint: disable=no-value-for-parameter


maybe_init()

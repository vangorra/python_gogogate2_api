#!/usr/bin/env python3
"""CLI for gogogate device."""
import asyncio
from enum import Enum
import pprint
from typing import Any, Optional, cast

import click
from gogogate2_api import GogoGate2Api

API = "api"
PRETTY_PRINT = pprint.PrettyPrinter(indent=4)


def is_named_tuple(obj: Any) -> bool:
    """Check if object is a named tuple."""
    _type = type(obj)
    bases = _type.__bases__
    if len(bases) != 1 or bases[0] != tuple:
        return False
    fields = getattr(_type, "_fields", None)
    if not isinstance(fields, tuple):
        return False
    return all(isinstance(field, str) for field in fields)


def unpack(obj: Any) -> Any:
    """Convert object."""
    if isinstance(obj, dict):
        return {key: unpack(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [unpack(value) for value in obj]
    if is_named_tuple(obj):
        return {key: unpack(value) for key, value in obj._asdict().items()}
    if isinstance(obj, tuple):
        return tuple(unpack(value) for value in obj)
    if isinstance(obj, Enum):
        return obj.value
    return obj


@click.group()
@click.option("--host", required=True)
@click.option("--username", required=True)
@click.option("--password", required=True)
@click.pass_context
def cli(
    ctx: Optional[click.core.Context] = None,
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    """Setup api."""
    ctx = cast(click.core.Context, ctx)
    ctx.obj = {
        API: GogoGate2Api(cast(str, host), cast(str, username), cast(str, password))
    }


@cli.command()
@click.pass_context
def info(ctx: click.core.Context) -> None:
    """Get info from device."""
    api: GogoGate2Api = ctx.obj[API]
    PRETTY_PRINT.pprint(
        unpack(asyncio.get_event_loop().run_until_complete(api.async_info()))
    )


@cli.command(name="open")
@click.argument("door_id", type=int, required=True)
@click.pass_context
def open_door(ctx: click.core.Context, door_id: int) -> None:
    """Open the door."""
    api: GogoGate2Api = ctx.obj[API]
    PRETTY_PRINT.pprint(
        unpack(
            asyncio.get_event_loop().run_until_complete(api.async_open_door(door_id))
        )
    )


@cli.command(name="close")
@click.argument("door_id", type=int, required=True)
@click.pass_context
def close_door(ctx: click.core.Context, door_id: int) -> None:
    """Close the door."""
    api: GogoGate2Api = ctx.obj[API]
    PRETTY_PRINT.pprint(
        unpack(
            asyncio.get_event_loop().run_until_complete(api.async_close_door(door_id))
        )
    )


if __name__ == "__main__":
    cli()
